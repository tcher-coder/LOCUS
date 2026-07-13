import os
import sys
import re
import yaml
import httpx
import asyncio
import logging
import subprocess
from datetime import datetime, date
from dotenv import load_dotenv

# Import our helper modules
from agent import run_locus_agent
from telegram_out import (
    send_rich_message,
    send_html_message,
    send_document,
    send_markdown_text,
    strip_markdown,
    build_post_parts,
    convert_md_to_html_fallback,
    escape_html
)
from archive import archive_post

# Setup data dir and logging
_DATA_DIR = os.getenv("LOCUS_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_DATA_DIR, exist_ok=True)
log_file = os.path.join(_DATA_DIR, "bridge.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
logger = logging.getLogger("locus.main")

# Load environment
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CLAUDE_CODE_OAUTH_TOKEN = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
TASK_TIMEOUT_SEC = int(os.getenv("TASK_TIMEOUT_MIN", "30")) * 60
# Фаза 2 (память/вики по Карпатому) временно отключена; вернуть — WIKI_ENABLED=1
WIKI_ENABLED = os.getenv("WIKI_ENABLED", "0").lower() in ("1", "true", "yes")

# ANTHROPIC_API_KEY перекрывает подписочную аутентификацию — убираем принудительно (EPIC 2.1)
if os.environ.pop("ANTHROPIC_API_KEY", None):
    logging.getLogger("locus.main").warning("ANTHROPIC_API_KEY удалён из окружения (перекрывал бы подписку)")

if not BOT_TOKEN or not OWNER_CHAT_ID:
    logger.critical("BOT_TOKEN and OWNER_CHAT_ID must be configured in bridge/.env")
    sys.exit(1)

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except ValueError:
    logger.critical("OWNER_CHAT_ID must be an integer")
    sys.exit(1)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(BASE_DIR, "vault")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Global state
queue = asyncio.Queue()
active_task = None
tasks_processed_today = 0
last_processed_date = date.today()
# Reply map: bot_message_id -> session_id (persisted to disk)
SESSION_MAP_FILE = os.path.join(_DATA_DIR, "session_map.json")

import json as _json

def _load_session_map() -> dict:
    if os.path.exists(SESSION_MAP_FILE):
        try:
            with open(SESSION_MAP_FILE, "r", encoding="utf-8") as f:
                raw = _json.load(f)
            # Keys must be ints (message_id); JSON stores them as strings
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.error(f"Error loading session_map: {e}")
    return {}

def _save_session_map():
    try:
        with open(SESSION_MAP_FILE, "w", encoding="utf-8") as f:
            _json.dump(reply_session_map, f, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving session_map: {e}")

reply_session_map = _load_session_map()

def get_token_info():
    """
    Returns setup-token release date information.
    """
    # Hardcoded or read from README
    token_issue_date = date(2026, 7, 13)
    days_left = 365 - (date.today() - token_issue_date).days
    return token_issue_date, days_left

def extract_tldr_from_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        return "Архивный документ"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip front-matter
        content_clean = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        # Look for TL;DR section or paragraph
        lines = content_clean.strip().splitlines()
        tldr_lines = []
        in_tldr = False
        for line in lines:
            line_strip = line.strip()
            if not line_strip:
                if tldr_lines:
                    break
                continue
            if "TL;DR" in line_strip or "Резюме" in line_strip:
                in_tldr = True
                # If the line has more than just the title, extract it
                t_part = re.sub(r'^.*?TL;DR[:\s\-]*', '', line_strip, flags=re.IGNORECASE)
                if t_part:
                    tldr_lines.append(t_part)
                continue
            if in_tldr:
                # Stop if we hit the next header
                if line_strip.startswith("#"):
                    break
                tldr_lines.append(line_strip)
        if tldr_lines:
            return "\n".join(tldr_lines).strip()
        # Fallback to first few non-empty lines after front-matter
        fallback_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")][:3]
        return "\n".join(fallback_lines)
    except Exception as e:
        logger.error(f"Error extracting TL;DR: {e}")
    return "Архивный документ"

def build_digest_from_file(file_path: str) -> list:
    """
    Готовит пост-выжимку для чата бота: суть сверху, разделы аккордеоном
    (<details>-плашки вместо оглавления). Длинные выжимки делятся на части
    «— Ч.N»; возвращает список Markdown-постов.
    """
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return build_post_parts(content)
    except Exception as e:
        logger.error(f"Error building digest from {file_path}: {e}")
        return []

async def handle_callback_query(cq: dict):
    cq_id = cq["id"]
    from_user = cq.get("from", {})
    user_id = from_user.get("id")
    
    if user_id != OWNER_CHAT_ID:
        logger.warning(f"Unauthorized callback query from {user_id}")
        await send_tg_api("answerCallbackQuery", {
            "callback_query_id": cq_id,
            "text": "Доступ запрещен!",
            "show_alert": True
        })
        return
        
    data = cq.get("data", "")
    logger.info(f"Received callback query {cq_id} with data: {data}")
    
    if data.startswith("get_file:"):
        slug = data[9:]
        # Find file in vault/raw/
        raw_dir = os.path.join(VAULT_DIR, "raw")
        matched_file = None
        if os.path.exists(raw_dir):
            for filename in os.listdir(raw_dir):
                if filename.endswith(".md") and slug in filename:
                    matched_file = filename
                    break
                
        if matched_file:
            # Answer callback query to stop loading state
            await send_tg_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "Отправка файла..."
            })
            # Send document
            doc_path = os.path.join(raw_dir, matched_file)
            send_document(OWNER_CHAT_ID, BOT_TOKEN, doc_path, caption=f"📄 {matched_file}")
        else:
            await send_tg_api("answerCallbackQuery", {
                "callback_query_id": cq_id,
                "text": "Файл не найден!",
                "show_alert": True
            })

async def handle_backfill_cmd(chat_id: int, status_msg_id: int):
    if not ARCHIVE_CHANNEL_ID:
        await edit_status_message(chat_id, status_msg_id, "❌ ARCHIVE_CHANNEL_ID не настроен в .env.")
        return

    raw_dir = os.path.join(VAULT_DIR, "raw")
    if not os.path.exists(raw_dir) or not os.listdir(raw_dir):
        await edit_status_message(chat_id, status_msg_id, "🗄️ Архив пуст, нечего переносить.")
        return

    from archive import load_archive_index, archive_post
    index = load_archive_index()
    
    files = [f for f in os.listdir(raw_dir) if f.endswith(".md")]
    to_post = [f for f in files if f not in index]
    
    if not to_post:
        await edit_status_message(chat_id, status_msg_id, "✅ Все файлы из архива уже загружены в канал.")
        return
        
    total = len(to_post)
    await edit_status_message(chat_id, status_msg_id, f"🔄 Начинаю backfill {total} файлов в канал...")
    
    posted_count = 0
    for idx, file in enumerate(to_post):
        rel_path = f"raw/{file}"

        logger.info(f"Backfilling {file} ({idx+1}/{total})...")
        success = False

        # Throttling and retry logic
        retries = 1
        while retries >= 0:
            success = archive_post(rel_path, BOT_TOKEN, ARCHIVE_CHANNEL_ID, VAULT_DIR)
            if success:
                posted_count += 1
                break
            else:
                logger.warning(f"Failed to post {file} during backfill. Retrying...")
                await asyncio.sleep(3)
                retries -= 1
                
        # Update progress in Telegram every 3 files or on completion
        if (idx + 1) % 3 == 0 or idx + 1 == total:
            await edit_status_message(chat_id, status_msg_id, f"🔄 Backfill в процессе: {idx+1}/{total} обработано, {posted_count} отправлено.")
            
        # Throttling delay between messages (Telegram channel limit is ~20 msg/min)
        await asyncio.sleep(3)
        
    await edit_status_message(chat_id, status_msg_id, f"✅ Backfill завершен! Обработано файлов: {total}, Успешно отправлено: {posted_count}.")

def read_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    if not os.path.exists(path):
        logger.error(f"Prompt template not found: {path}")
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def parse_yaml_front_matter(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        logger.error(f"Error parsing YAML front matter from {file_path}: {e}")
    return {}

def run_git_command(cwd, args):
    try:
        logger.info(f"Running git command in {cwd}: git {' '.join(args)}")
        res = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Git command failed: stderr={e.stderr!r} stdout={e.stdout!r}")
        raise

def commit_vault_changes(rel_path, prefix="Ingested"):
    """
    Adds and commits changes to the vault repository.
    Message matches the document title if available.
    """
    abs_path = os.path.join(VAULT_DIR, rel_path)
    title = "Updated base"

    if os.path.exists(abs_path) and rel_path.startswith("raw/"):
        meta = parse_yaml_front_matter(abs_path)
        title = meta.get("title", f"Ingested {os.path.basename(rel_path)}")

    try:
        run_git_command(VAULT_DIR, ["add", "."])
        run_git_command(VAULT_DIR, ["commit", "-m", f"{prefix}: {title}"])
        logger.info(f"Committed changes for {rel_path} in vault")
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in (e.stdout or ""):
            logger.info(f"Vault: nothing to commit ({prefix}: {title})")
        else:
            logger.error(f"Failed to commit changes in vault: {e}")
    except Exception as e:
        logger.error(f"Failed to commit changes in vault: {e}")

async def send_tg_api(method: str, payload: dict) -> httpx.Response:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    async with httpx.AsyncClient() as client:
        return await client.post(url, json=payload, timeout=20)

async def edit_status_message(chat_id: int, message_id: int, text: str):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    await send_tg_api("editMessageText", payload)

async def process_task(task: dict):
    global tasks_processed_today, last_processed_date
    
    # Update date counter if needed
    if date.today() != last_processed_date:
        tasks_processed_today = 0
        last_processed_date = date.today()

    chat_id = task["chat_id"]
    text = task["text"].strip()
    reply_to_id = task.get("reply_to_message_id")
    
    # Send initial status
    res = await send_tg_api("sendMessage", {
        "chat_id": chat_id,
        "text": "⏳ Инициализация агента...",
        "reply_to_message_id": task["message_id"]
    })
    if res.status_code != 200:
        logger.error(f"Failed to send initial status: {res.text}")
        return
        
    status_msg_id = res.json()["result"]["message_id"]

    # Determine command/type
    is_command = text.startswith("/")
    cmd_name = text.split()[0].lower() if is_command else ""
    
    # Extract flags
    is_deep = "+deep" in text
    text_clean = text.replace("+deep", "").strip()
    
    effort = "medium" if is_deep else "low"
    
    # Handle Dialog resume
    resume_id = None
    if reply_to_id and reply_to_id in reply_session_map:
        resume_id = reply_session_map[reply_to_id]
        logger.info(f"Resuming session {resume_id} for message reply {reply_to_id}")

    prompt = ""
    is_ask_only = False
    is_lint = False
    
    if resume_id:
        # Standard follow-up
        prompt = text_clean
    elif cmd_name == "/ask":
        is_ask_only = True
        question = text_clean[5:].strip()
        if not question:
            await edit_status_message(chat_id, status_msg_id, "❌ Пожалуйста, введите вопрос после /ask.")
            return
        template = read_prompt_template("ask_wiki.md")
        prompt = template.replace("{{QUESTION}}", question)
    elif cmd_name == "/lint":
        is_ask_only = True
        is_lint = True
        prompt = "Выполните ручную гигиену вики по AGENTS.md. Найдите дубликаты, битые ссылки, устаревшую информацию. Исправьте найденные проблемы и выведите отчёт."
    elif cmd_name == "/digest":
        # No agent needed! Reading log.md directly.
        log_path = os.path.join(VAULT_DIR, "wiki/log.md")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            digest = escape_html("".join(lines[-25:]))[:3800]
            await send_tg_api("editMessageText", {
                "chat_id": chat_id,
                "message_id": status_msg_id,
                "text": f"<b>Сводка изменений (wiki/log.md):</b>\n\n{digest}",
                "parse_mode": "HTML"
            })
        else:
            await edit_status_message(chat_id, status_msg_id, "❌ Файл wiki/log.md не найден.")
        return
    elif cmd_name == "/stats":
        token_date, days_left = get_token_info()
        stats_text = (
            f"📊 <b>Статистика LOCUS:</b>\n\n"
            f"• Обработано задач сегодня: {tasks_processed_today}\n"
            f"• Задач в очереди: {queue.qsize()}\n"
            f"• Дата выпуска токена: {token_date.strftime('%Y-%m-%d')}\n"
            f"• Дней до обновления токена: {days_left}\n"
        )
        if days_left <= 30:
            stats_text += f"\n⚠️ <b>ВНИМАНИЕ: Срок действия токена истекает через {days_left} дн.! Обновите его через 'claude setup-token'.</b>"
            
        await send_tg_api("editMessageText", {
            "chat_id": chat_id,
            "message_id": status_msg_id,
            "text": stats_text,
            "parse_mode": "HTML"
        })
        return
    elif cmd_name == "/archive":
        # Get count N
        parts = text_clean.split()
        n_val = 10
        if len(parts) > 1:
            try:
                n_val = int(parts[1])
                n_val = max(1, min(n_val, 50))
            except ValueError:
                pass
        
        raw_dir = os.path.join(VAULT_DIR, "raw")
        if not os.path.exists(raw_dir) or not os.listdir(raw_dir):
            await edit_status_message(chat_id, status_msg_id, "🗄️ Архив пуст.")
            return

        # List files in raw sorted by name descending (latest date first)
        files = [f for f in os.listdir(raw_dir) if f.endswith(".md")]
        files.sort(reverse=True)
        latest_files = files[:n_val]

        keyboard = []
        text_lines = ["🗄️ <b>Последние документы в архиве:</b>\n"]
        for idx, file in enumerate(latest_files):
            meta = parse_yaml_front_matter(os.path.join(raw_dir, file))
            title = meta.get("title", file)
            dtype = meta.get("type", "text")
            date_str = meta.get("date_ingested", file[:10])
            
            type_emoji = "📹" if dtype == "video" else "📄" if dtype == "article" else "✍️"
            text_lines.append(f"{idx+1}. {type_emoji} <code>{date_str}</code> · {title}")
            
            slug = file.replace(".md", "")
            keyboard.append([{"text": f"⬇️ Скачать файл {idx+1}", "callback_data": f"get_file:{slug}"[:64]}])

        await send_tg_api("editMessageText", {
            "chat_id": chat_id,
            "message_id": status_msg_id,
            "text": "\n".join(text_lines),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        })
        return

    elif cmd_name == "/find":
        query_words = text_clean[5:].strip()
        if not query_words:
            await edit_status_message(chat_id, status_msg_id, "❌ Пожалуйста, введите поисковый запрос после /find.")
            return
            
        raw_dir = os.path.join(VAULT_DIR, "raw")
        if not os.path.exists(raw_dir):
            await edit_status_message(chat_id, status_msg_id, "🗄️ Архив пуст.")
            return

        matched = []
        # Search in all md files
        for file in os.listdir(raw_dir):
            if not file.endswith(".md"):
                continue
            abs_file = os.path.join(raw_dir, file)
            with open(abs_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            if re.search(re.escape(query_words), content, re.IGNORECASE):
                # find first line with match for snippet
                snippet = ""
                for line in content.splitlines():
                    if re.search(re.escape(query_words), line, re.IGNORECASE):
                        # extract snippet and escape html
                        snippet = line.strip()
                        # strip front matter lines if matched
                        if not snippet.startswith(("-", "url:", "type:", "title:", "author:", "date_ingested:", "tags:")):
                            snippet = escape_html(snippet)
                            if len(snippet) > 80:
                                snippet = snippet[:80] + "..."
                            break
                
                meta = parse_yaml_front_matter(abs_file)
                title = meta.get("title", file)
                dtype = meta.get("type", "text")
                matched.append({
                    "file": file,
                    "title": title,
                    "type": dtype,
                    "snippet": snippet
                })
                if len(matched) >= 10:
                    break

        if not matched:
            await edit_status_message(chat_id, status_msg_id, f"❌ Совпадений по запросу '{query_words}' не найдено.")
            return

        keyboard = []
        text_lines = [f"🔍 <b>Результаты поиска по запросу '{query_words}':</b>\n"]
        for idx, item in enumerate(matched):
            type_emoji = "📹" if item["type"] == "video" else "📄" if item["type"] == "article" else "✍️"
            snippet_str = f"\n   <i>\"{item['snippet']}\"</i>" if item["snippet"] else ""
            text_lines.append(f"{idx+1}. {type_emoji} <b>{item['title']}</b>{snippet_str}")
            
            slug = item["file"].replace(".md", "")
            keyboard.append([{"text": f"⬇️ Скачать файл {idx+1}", "callback_data": f"get_file:{slug}"[:64]}])

        await send_tg_api("editMessageText", {
            "chat_id": chat_id,
            "message_id": status_msg_id,
            "text": "\n".join(text_lines),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        })
        return

    elif cmd_name == "/get":
        slug = text_clean[4:].strip()
        if not slug:
            await edit_status_message(chat_id, status_msg_id, "❌ Пожалуйста, введите имя или часть имени файла после /get.")
            return
            
        raw_dir = os.path.join(VAULT_DIR, "raw")
        if not os.path.exists(raw_dir):
            await edit_status_message(chat_id, status_msg_id, "🗄️ Архив пуст.")
            return

        matches = [f for f in os.listdir(raw_dir) if f.endswith(".md") and slug.lower() in f.lower()]
        
        if not matches:
            await edit_status_message(chat_id, status_msg_id, f"❌ Файл по запросу '{slug}' не найден.")
            return
            
        if len(matches) == 1:
            file_path = os.path.join(raw_dir, matches[0])
            # Delete status message
            await send_tg_api("deleteMessage", {"chat_id": chat_id, "message_id": status_msg_id})
            send_document(chat_id, BOT_TOKEN, file_path, caption=f"📄 {matches[0]}")
            return
            
        # Multiple matches
        keyboard = []
        text_lines = [f"❓ Найдено несколько совпадений для '{slug}':\n"]
        for idx, file in enumerate(matches[:10]):
            meta = parse_yaml_front_matter(os.path.join(raw_dir, file))
            title = meta.get("title", file)
            text_lines.append(f"{idx+1}. <code>{file}</code> · {title}")
            
            file_slug = file.replace(".md", "")
            keyboard.append([{"text": f"📄 Скачать {idx+1}", "callback_data": f"get_file:{file_slug}"[:64]}])

        await send_tg_api("editMessageText", {
            "chat_id": chat_id,
            "message_id": status_msg_id,
            "text": "\n".join(text_lines),
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}
        })
        return

    elif cmd_name == "/backfill":
        await handle_backfill_cmd(chat_id, status_msg_id)
        return

    elif is_command:
        # Неизвестная команда (/start, /help, опечатки) — НЕ запускать агента
        help_text = (
            "🤖 <b>LOCUS</b> — агент «ссылка → знание».\n\n"
            "Пришли <b>ссылку</b> (статья/видео) или <b>текст</b> — получишь конспект, "
            "база знаний обновится автоматически.\n"
            "Флаги: <code>+deep</code> (глубокий анализ), <code>+frames</code> (кадры видео).\n\n"
            "<b>Команды:</b>\n"
            "/ask &lt;вопрос&gt; — вопрос к базе знаний\n"
            "/digest — последние изменения вики\n"
            "/archive [N] — последние документы\n"
            "/find &lt;слова&gt; — поиск по конспектам\n"
            "/get &lt;имя&gt; — документ файлом\n"
            "/backfill — догрузить архивный канал\n"
            "/lint — гигиена вики\n"
            "/stats — статистика"
        )
        await send_tg_api("editMessageText", {
            "chat_id": chat_id, "message_id": status_msg_id,
            "text": help_text, "parse_mode": "HTML"
        })
        return

    else:
        # Ingest flow (Article / Video / Text)
        urls = re.findall(r'(https?://\S+)', text_clean)
        
        if urls:
            url = urls[0]
            # Check if video
            is_video = any(domain in url.lower() for domain in ["youtube.com", "youtu.be", "tiktok.com", "vimeo.com", "x.com"])
            instructions = text_clean.replace(url, "").strip()
            
            if is_video:
                template = read_prompt_template("ingest_video.md")
                frames_enabled = "True" if "+frames" in text else "False"
                instructions = instructions.replace("+frames", "").strip()
                prompt = template.replace("{{URL}}", url).replace("{{FRAMES_ENABLED}}", frames_enabled).replace("{{INSTRUCTIONS}}", instructions or "none")
            else:
                template = read_prompt_template("ingest_article.md")
                prompt = template.replace("{{URL}}", url).replace("{{INSTRUCTIONS}}", instructions or "none")
        else:
            # Raw text
            template = read_prompt_template("ingest_text.md")
            prompt = template.replace("{{TEXT}}", text_clean).replace("{{INSTRUCTIONS}}", "none")

    # Run the Agent
    captured_session_id = None
    full_output = ""
    status_emoji_map = {
        "started": "⏳ Инициализация...",
        "reading": "📖 Читаю источник...",
        "conspecting": "✍️ Конспектирую...",
        "updating_wiki": "🗂️ Обновляю базу знаний...",
        "finished": "✅ Почти готово..."
    }

    try:
        # Run agent calling helper with retry for network errors
        retries = 1
        success = False
        result_event = None

        while retries >= 0:
            try:
                async with asyncio.timeout(TASK_TIMEOUT_SEC):
                    async for event in run_locus_agent(prompt, VAULT_DIR, effort, GROQ_API_KEY, resume_session_id=resume_id):
                        if event["type"] == "status":
                            status_text = status_emoji_map.get(event["status"], "⏳ Обработка...")
                            await edit_status_message(chat_id, status_msg_id, status_text)
                        elif event["type"] == "session_id":
                            captured_session_id = event["session_id"]
                        elif event["type"] == "result":
                            result_event = event
                            full_output = event["text"]
            except TimeoutError:
                result_event = {"success": False, "error": f"Задача превысила таймаут {TASK_TIMEOUT_SEC // 60} мин и была прервана.", "text": full_output}
                    
            if result_event and result_event["success"]:
                success = True
                break
            else:
                # Check for rate limit or network error
                err_text = result_event["error"] if result_event else "Unknown error"
                if "rate limit" in err_text.lower() or "429" in err_text:
                    await edit_status_message(chat_id, status_msg_id, "⚠️ Достигнуты лимиты подписки Pro. Ожидание сброса лимитов (60 секунд)...")
                    await asyncio.sleep(60)
                    retries -= 1
                    await edit_status_message(chat_id, status_msg_id, "⏳ Повторный запуск...")
                else:
                    break # Don't retry non-ratelimit errors

        if not success:
            err_text = result_event["error"] if result_event else "Unknown error"
            await edit_status_message(chat_id, status_msg_id, f"❌ Ошибка выполнения агента:\n\n{err_text}")
            return

        # Parse markers from final text.
        # ВАЖНО: терпимы к оформлению — агент может обернуть маркер в **жирный**,
        # `код`, цитату или сдвинуть пробелами.
        marker_res = r'^[\s>*_`#-]*RESULT[\s*_`]*:[\s*_`]*(\S+)'
        marker_sum = r'^[\s>*_`#-]*SUMMARY[\s*_`]*:\s*(.+)$'
        res_matches = [m.strip('`*_') for m in re.findall(marker_res, full_output, re.MULTILINE)]
        sum_matches = [m.strip('`*_ ') for m in re.findall(marker_sum, full_output, re.MULTILINE)]

        result_val = res_matches[-1] if res_matches else "NONE"
        summary_val = sum_matches[-1] if sum_matches else full_output[:300] + "..."

        if not res_matches:
            # Диагностика: маркер не найден — сохраняем хвост ответа агента в лог
            logger.warning(f"RESULT marker not found. Agent output tail: {full_output[-600:]!r}")

        # Нормализация пути: агент может добавить префикс ./ или vault/
        if result_val != "NONE":
            result_val = re.sub(r'^(\./)+|^vault/', '', result_val)
            if not os.path.exists(os.path.join(VAULT_DIR, result_val)):
                logger.warning(f"RESULT file does not exist: {result_val}")
                result_val = "NONE"

        if result_val == "NONE":
            # Sitemap confirmation or error
            await send_tg_api("editMessageText", {
                "chat_id": chat_id,
                "message_id": status_msg_id,
                "text": f"ℹ️ <b>Уведомление агента:</b>\n\n{escape_html(summary_val)}",
                "parse_mode": "HTML"
            })
            # If sitemap confirmation, save to map
            if captured_session_id:
                reply_session_map[status_msg_id] = captured_session_id
                _save_session_map()
                logger.info(f"Saved session ID {captured_session_id} for bot message {status_msg_id}")
            return

        # Success! Deliver files & rich messages
        await edit_status_message(chat_id, status_msg_id, "📤 Доставка результатов...")
        
        # Determine files to send
        if is_ask_only:
            # Just send text response in HTML or RichMessage
            success_sent = send_rich_message(chat_id, BOT_TOKEN, full_output)
            if not success_sent:
                html_fallback = convert_md_to_html_fallback(full_output)
                send_html_message(chat_id, BOT_TOKEN, html_fallback)
            # /lint modifies wiki files — commit them
            if is_lint:
                commit_vault_changes("wiki/")
            # Delete status message
            await send_tg_api("deleteMessage", {"chat_id": chat_id, "message_id": status_msg_id})
        else:
            # Full ingest delivery (фаза 1 завершена: конспект создан)
            doc_abs_path = os.path.join(VAULT_DIR, result_val)

            # 1. Выжимка текстом прямо в чат (без файла), длинная — частями «Ч.N».
            #    message_id частей собираем: реплай на любую часть продолжит сессию.
            digest_parts = build_digest_from_file(doc_abs_path)
            digest_msg_ids = []
            if digest_parts:
                for part in digest_parts:
                    send_markdown_text(chat_id, BOT_TOKEN, part, sent_ids=digest_msg_ids)
            else:
                # Фолбэк: если выжимку не удалось подготовить — отправляем файл
                send_document(chat_id, BOT_TOKEN, doc_abs_path, caption=f"📄 {os.path.basename(result_val)}")

            # 2. Архивный канал: rich-пост с выжимкой и хэштегами (файлы .md
            #    боты Telegram отдают с кривым MIME — читать их в TG нельзя)
            if ARCHIVE_CHANNEL_ID:
                try:
                    archive_post(result_val, BOT_TOKEN, ARCHIVE_CHANNEL_ID, VAULT_DIR)
                except Exception as ae:
                    logger.error(f"Error posting to archive channel: {ae}")

            # 3. Git commit конспекта
            commit_vault_changes(result_val)
            tasks_processed_today += 1

            # 4. Фаза 2: обновление вики (память) — ПОСЛЕ доставки, чтобы не заставлять ждать
            wiki_ok = False
            if WIKI_ENABLED and captured_session_id:
                await edit_status_message(chat_id, status_msg_id,
                                          "🧠 Конспект доставлен. Обновляю базу знаний (память)...")
                wiki_prompt = read_prompt_template("update_wiki.md").replace("{{DOC_PATH}}", result_val)
                try:
                    async with asyncio.timeout(TASK_TIMEOUT_SEC):
                        async for event in run_locus_agent(wiki_prompt, VAULT_DIR, effort, GROQ_API_KEY,
                                                           resume_session_id=captured_session_id):
                            if event["type"] == "session_id":
                                captured_session_id = event["session_id"]
                            elif event["type"] == "result":
                                wiki_ok = event["success"]
                                if not wiki_ok:
                                    logger.error(f"Wiki update phase failed: {event.get('error')}")
                except TimeoutError:
                    logger.error("Wiki update phase timed out")
                except Exception as we:
                    logger.exception(f"Wiki update phase error: {we}")
                if wiki_ok:
                    commit_vault_changes(result_val, prefix="Wiki update")

            # 5. Привязать сессию к статус-сообщению и всем частям выжимки —
            #    реплай на любое из них продолжит диалог с агентом
            if captured_session_id:
                reply_session_map[status_msg_id] = captured_session_id
                for mid in digest_msg_ids:
                    reply_session_map[mid] = captured_session_id
                _save_session_map()
                if not WIKI_ENABLED:
                    wiki_note = "память отключена"
                elif wiki_ok:
                    wiki_note = "память обновлена"
                else:
                    wiki_note = "⚠️ память НЕ обновлена (см. логи)"
                await edit_status_message(chat_id, status_msg_id,
                                          f"✅ Готово: конспект доставлен, {wiki_note}. "
                                          "Ответь реплаем на это сообщение, чтобы продолжить сессию.")
            else:
                # Delete status message
                await send_tg_api("deleteMessage", {"chat_id": chat_id, "message_id": status_msg_id})

    except Exception as e:
        logger.exception("Error during task execution")
        await edit_status_message(chat_id, status_msg_id, f"❌ Произошла системная ошибка при обработке: {e}")

async def polling_loop():
    offset = 0
    logger.info("Starting Telegram long polling loop...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"offset": offset, "timeout": 30}
            
            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, timeout=35)
                
            if res.status_code != 200:
                logger.error(f"getUpdates status {res.status_code}: {res.text}")
                await asyncio.sleep(5)
                continue
                
            updates = res.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                
                callback_query = update.get("callback_query")
                if callback_query:
                    try:
                        await handle_callback_query(callback_query)
                    except Exception as cq_err:
                        logger.error(f"Error handling callback query: {cq_err}")
                    continue
                    
                message = update.get("message")
                if not message:
                    continue
                    
                from_user = message.get("from", {})
                user_id = from_user.get("id")
                
                # Check owner limit
                if user_id != OWNER_CHAT_ID:
                    logger.warning(f"Ignored message from unauthorized user {user_id} (@{from_user.get('username')})")
                    continue
                    
                # Диагностика: метаданные присланных/пересланных документов
                if message.get("document"):
                    logger.info(f"Incoming document metadata: {message['document']}")

                text = message.get("text")
                if not text:
                    continue
                    
                message_id = message["message_id"]
                reply_to = message.get("reply_to_message")
                reply_to_msg_id = reply_to["message_id"] if reply_to else None
                
                # Add to queue
                task = {
                    "chat_id": OWNER_CHAT_ID,
                    "message_id": message_id,
                    "text": text,
                    "reply_to_message_id": reply_to_msg_id
                }
                
                queue_size = queue.qsize()
                if queue_size > 0 or active_task is not None:
                    # Notify about queue position
                    await send_tg_api("sendMessage", {
                        "chat_id": OWNER_CHAT_ID,
                        "text": f"⏳ Принято! Ваша задача добавлена в очередь (позиция {queue_size + 1}).",
                        "reply_to_message_id": message_id
                    })
                    
                await queue.put(task)
                logger.info(f"Queued task {message_id}, queue size = {queue.qsize()}")
                
        except httpx.RequestError as e:
            logger.error(f"Network error in getUpdates: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.exception("Unexpected error in polling loop")
            await asyncio.sleep(5)

async def queue_worker():
    global active_task
    logger.info("Starting Queue Worker task...")
    
    while True:
        task = await queue.get()
        active_task = task
        logger.info(f"Processing task from queue: message {task['message_id']}")
        try:
            await process_task(task)
        except Exception as e:
            logger.exception(f"Error processing task {task['message_id']}")
        finally:
            active_task = None
            queue.task_done()

async def register_commands():
    commands = [
        {"command": "ask", "description": "Задать вопрос по базе знаний (ИИ)"},
        {"command": "lint", "description": "Запустить гигиену базы знаний (ИИ)"},
        {"command": "archive", "description": "Показать последние конспекты (локально)"},
        {"command": "find", "description": "Поиск по тексту конспектов (локально)"},
        {"command": "get", "description": "Скачать конспект по названию (локально)"},
        {"command": "digest", "description": "Показать лог изменений базы (локально)"},
        {"command": "backfill", "description": "Догрузить файлы в архивный канал (локально)"},
        {"command": "stats", "description": "Показать статистику за сегодня и токен"}
    ]
    logger.info("Registering bot commands in Telegram...")
    try:
        response = await send_tg_api("setMyCommands", {"commands": commands})
        if response.status_code == 200 and response.json().get("ok"):
            logger.info("Bot commands registered successfully!")
        else:
            logger.error(f"Failed to register bot commands: {response.text}")
    except Exception as e:
        logger.error(f"Error registering bot commands: {e}")

async def main():
    # Register commands at startup
    await register_commands()
    
    # Run polling loop and queue worker concurrently
    await asyncio.gather(
        polling_loop(),
        queue_worker()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user.")

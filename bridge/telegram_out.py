import os
import re
import httpx
import logging

logger = logging.getLogger("locus.telegram_out")

def escape_html(text: str) -> str:
    """Escapes HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def strip_markdown(text: str) -> str:
    """
    Убирает Markdown-разметку, оставляя чистый текст.
    Используется для TL;DR-подписи в архивном канале (без рич-разметки).
    """
    t = text
    t = re.sub(r'```[a-zA-Z]*\n?', '', t)
    t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'__(.*?)__', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'(?<!\w)_(.*?)_(?!\w)', r'\1', t)
    t = re.sub(r'`([^`]*)`', r'\1', t)
    t = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', t)
    t = re.sub(r'^\s*>\s?', '', t, flags=re.MULTILINE)
    return t.strip()

def _paragraphs_to_h4(content: str) -> str:
    """
    ЭКСПЕРИМЕНТ: обычные текстовые абзацы рендерим H4-заголовком (####) —
    у rich-сообщений тело крупнее обычного, H4 визуально ближе к норме.
    Списки, таблицы, цитаты, код и готовые заголовки не трогаем.
    Вызывается ПОСЛЕ разбиения на секции, чтобы #### не стали плашками.
    """
    out_blocks = []
    in_fence = False
    for block in re.split(r'\n\s*\n', content):
        lines = [l for l in block.splitlines() if l.strip()]
        has_fence = any(l.strip().startswith("```") for l in lines)
        is_plain = (
            not in_fence and not has_fence and lines
            and all(not re.match(r'^\s*([-*>|#+]|\d+[.)]\s|```)', l) for l in lines)
        )
        if has_fence and len([l for l in lines if l.strip().startswith("```")]) % 2 == 1:
            in_fence = not in_fence
        if is_plain:
            out_blocks.append("#### " + " ".join(l.strip() for l in lines))
        else:
            out_blocks.append(block)
    return "\n\n".join(out_blocks)

# Раздел «Ключевые идеи»: плашка раскрыта по умолчанию, маркеры вместо цифр
KEY_IDEAS_RE = re.compile(r'ключев', re.IGNORECASE)

def build_accordion_blocks(md_body: str) -> list:
    """
    Превращает Markdown-разделы в список блоков плоского аккордеона:
    преамбула (текст до первого заголовка, оформленный цитатой) и
    <details>-плашки — по блоку на каждый заголовок (##/###/…).
    Вложенность НЕ используется — она ломает структуру в Telegram.
    Заголовки-контейнеры без собственного текста (например «Выжимка»,
    у которой всё в подразделах) опускаются.
    """
    segments = []  # (заголовок или None для преамбулы, строки контента)
    heading, buf = None, []
    in_fence = False
    for line in md_body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            buf.append(line)
            continue
        m = None if in_fence else re.match(r'^(#{2,6})\s+(.*)$', s)
        if m:
            segments.append((heading, buf))
            heading, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    segments.append((heading, buf))

    res = []
    for head, lines in segments:
        content = "\n".join(lines).strip()
        if head is None:
            if content:
                res.append(_preamble_transform(content))
        elif content:
            # Заголовок плашки жирным, иначе он рендерится мельче основного текста
            head_clean = escape_html(strip_markdown(head))
            if KEY_IDEAS_RE.search(head):
                # Ключевые идеи: цифры → маркеры; свёрнуты, как и остальные плашки
                content = re.sub(r'^(\s*)\d+[.)]\s+', r'\1- ', content, flags=re.MULTILINE)
            else:
                content = _paragraphs_to_h4(content)
            res.append(f"<details><summary><b>{head_clean}</b></summary>\n\n{content}\n\n</details>")
    return res

def _preamble_transform(content: str) -> str:
    """
    Преамбула (название + TL;DR): текстовые абзацы оформляем блок-цитатой,
    заголовок и дивайдеры не трогаем.
    """
    out_blocks = []
    for block in re.split(r'\n\s*\n', content):
        lines = [l for l in block.splitlines() if l.strip()]
        if lines and all(not re.match(r'^\s*([-*>|#]|\d+[.)]\s|```)', l) for l in lines):
            out_blocks.append("> " + " ".join(l.strip() for l in lines))
        else:
            out_blocks.append(block)
    return "\n\n".join(out_blocks)

# Порог деления поста на части — почти весь лимит rich-сообщения Bot API
# (32 768): части режем как можно реже, только когда пост не влезает
# в одно сообщение; блок, не влезающий целиком, уходит в следующую часть.
# Чуть ниже RICH_MESSAGE_MAX_LEN, чтобы готовая часть с шапкой и финальным
# дивайдером гарантированно не пересобиралась при отправке.
POST_PART_MAX_LEN = 31500

def _title_header(title: str, part_no: int = 0) -> str:
    """Шапка поста: дивайдеры до и после названия (капсом), опц. номер части."""
    suffix = f" — Ч.{part_no}" if part_no else ""
    return f"---\n\n# {title}{suffix}\n\n---"

def build_post_parts(content: str, max_len: int = POST_PART_MAX_LEN) -> list:
    """
    Из содержимого raw-конспекта (с front-matter) готовит Telegram-пост:
    шапка с названием капсом в дивайдерах, суть цитатой (TL;DR без ярлыка),
    ниже — разделы аккордеоном, дивайдер в конце.
    Длинный пост делится на части по границам плашек: каждая часть получает
    ту же шапку с пометкой «— Ч.N». Возвращает список Markdown-постов.
    """
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    # Убираем раздел "Оглавление"/"Содержание" целиком
    body = re.sub(
        r'^#{1,4}\s*(Оглавление|Содержание)\b.*?(?=^#{1,4}\s|\Z)',
        '', body, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    # Заголовок TL;DR убираем, сам текст сути остаётся открытым сверху
    body = re.sub(r'^#{1,4}\s*TL;?DR\s*:?\s*$\n?', '', body,
                  flags=re.MULTILINE | re.IGNORECASE)
    # Вики-ссылки [[Имя]] не кликабельны в TG — показываем жирным
    body = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'**\1**', body)

    # Название выносим из тела: оно капсом уходит в шапку каждой части
    title = ""
    m = re.search(r'^#\s+(.+)$', body, flags=re.MULTILINE)
    if m:
        title = strip_markdown(m.group(1)).upper()
        body = body[:m.start()] + body[m.end():]

    blocks = build_accordion_blocks(body.strip())

    # Группируем блоки в части: плашки не режем, преамбула — всегда в первой
    groups, current, current_len = [], [], 0
    header_len = len(_title_header(title, 9))
    for block in blocks:
        if current and current_len + len(block) > max_len - header_len:
            groups.append(current)
            current, current_len = [], 0
        current.append(block)
        current_len += len(block) + 2
    if current:
        groups.append(current)
    if not groups:
        groups = [[]]

    multi = len(groups) > 1
    parts = []
    for i, group in enumerate(groups, 1):
        header = _title_header(title, i if multi else 0) if title else ""
        chunk = "\n\n".join([header] + group if header else group)
        parts.append(chunk + "\n\n---")
    return parts

def build_post_from_document(content: str) -> str:
    """Пост одной строкой (для коротких документов и обратной совместимости)."""
    return "\n\n".join(build_post_parts(content, max_len=10**9))

# Лимит rich-сообщения по Bot API 10.1 — 32768 символов; берём с запасом.
RICH_MESSAGE_MAX_LEN = 32000

def split_markdown_chunks(md_text: str, max_len: int = RICH_MESSAGE_MAX_LEN) -> list:
    """
    Режет Markdown на части не длиннее max_len по границам блоков (пустым строкам),
    чтобы каждую часть можно было отправить отдельным сообщением.
    """
    chunks = []
    current = ""
    for block in re.split(r'\n\s*\n', md_text):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
        # Одиночный блок длиннее лимита — режем жёстко
        while len(current) > max_len:
            chunks.append(current[:max_len])
            current = current[max_len:]
    if current.strip():
        chunks.append(current)
    return chunks

def send_markdown_text(chat_id: int, bot_token: str, md_text: str, sent_ids: list = None) -> bool:
    """
    Отправляет Markdown-текст в чат rich-сообщениями (HTML-фолбэка нет —
    решение владельца, 2026-07). Текст длиннее лимита rich-сообщения
    разбивается на несколько сообщений по границам блоков.
    В sent_ids (если передан список) складываются message_id всех отправленных
    сообщений — для привязки реплай-сессий.
    """
    all_ok = True
    for chunk in split_markdown_chunks(md_text):
        mid = send_rich_message(chat_id, bot_token, chunk)
        if mid:
            if sent_ids is not None and isinstance(mid, int):
                sent_ids.append(mid)
        else:
            all_ok = False
    return all_ok

def send_rich_message(chat_id: int, bot_token: str, md_content: str) -> bool:
    """
    Sends a Rich Message to Telegram Bot API 10.1 using raw HTTP.
    InputRichMessage принимает Markdown-строку напрямую (поле `markdown`) —
    Telegram сам парсит заголовки, списки, таблицы, цитаты и код.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"
    try:
        payload = {
            "chat_id": chat_id,
            "rich_message": {"markdown": md_content}
        }
        logger.info(f"Sending rich message to chat {chat_id}")
        response = httpx.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            logger.info("Rich message sent successfully.")
            # message_id — истинное значение; True как фолбэк, если тела нет
            try:
                return response.json()["result"]["message_id"]
            except Exception:
                return True
        else:
            logger.error(f"Failed to send rich message (status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in send_rich_message: {e}")
        return False

def send_document(chat_id: int, bot_token: str, file_path: str, caption: str = "") -> bool:
    """
    Sends a local file as a document.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    try:
        filename = os.path.basename(file_path)
        logger.info(f"Sending document {filename} to chat {chat_id}")

        with open(file_path, "rb") as f:
            content = f.read()
        # Явный MIME text/markdown — без него Telegram считает файл бинарным
        # (octet-stream) и ломает предпросмотр/кодировку.
        mime = "text/markdown" if filename.lower().endswith(".md") else None
        files = {"document": (filename, content, mime) if mime else (filename, content)}
        data = {"chat_id": chat_id, "caption": caption}
        response = httpx.post(url, data=data, files=files, timeout=30)

        if response.status_code == 200:
            logger.info("Document sent successfully.")
            return True
        else:
            logger.error(f"Failed to send document (status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in send_document: {e}")
        return False

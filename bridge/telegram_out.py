import os
import re
import httpx
import logging

logger = logging.getLogger("locus.telegram_out")

def escape_html(text: str) -> str:
    """Escapes HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def convert_md_to_html_fallback(md_text: str) -> str:
    """
    Very simple Markdown to HTML converter for standard TG fallback message.
    """
    # Replace bold, italic, code
    text = escape_html(md_text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    # Replace links
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
    return text

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

def build_accordion_md(md_body: str) -> str:
    """
    Превращает Markdown-разделы в плоский аккордеон из <details>-плашек:
    каждый заголовок (##/###/…) становится <summary> плашки верхнего уровня,
    контент скрыт до клика. Вложенность НЕ используется — она ломает
    структуру в Telegram. Заголовки-контейнеры без собственного текста
    (например «Выжимка», у которой всё в подразделах) опускаются.
    Текст до первого заголовка (название и суть) остаётся открытым сверху.
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
                res.append(content)
        elif content:
            res.append(f"<details><summary>{head}</summary>\n\n{content}\n\n</details>")
    return "\n\n".join(res)

def build_post_from_document(content: str) -> str:
    """
    Из содержимого raw-конспекта (с front-matter) готовит Telegram-пост:
    сверху суть (текст TL;DR без ярлыка), ниже — разделы аккордеоном.
    Оглавление убирается: роль оглавления играют свёрнутые плашки.
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
    return build_accordion_md(body.strip())

# Лимит rich-сообщения по Bot API 10.1 — 32768 символов; берём с запасом.
RICH_MESSAGE_MAX_LEN = 30000

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

def send_markdown_text(chat_id: int, bot_token: str, md_text: str) -> bool:
    """
    Отправляет Markdown-текст в чат: rich-сообщениями, при неудаче — HTML-фолбэк.
    Текст длиннее лимита rich-сообщения разбивается на несколько сообщений.
    """
    all_ok = True
    for chunk in split_markdown_chunks(md_text):
        if not send_rich_message(chat_id, bot_token, chunk):
            # HTML-фолбэк ограничен 4096 символами — режем мельче
            for sub in split_markdown_chunks(chunk, max_len=3800):
                if not send_html_message(chat_id, bot_token, convert_md_to_html_fallback(sub)):
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
            return True
        else:
            logger.error(f"Failed to send rich message (status {response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error in send_rich_message: {e}")
        return False

def send_html_message(chat_id: int, bot_token: str, text: str) -> bool:
    """
    Sends a standard Telegram message with HTML parsing.
    Truncates text to 4096 characters.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    # Truncate to 4096 characters safely
    if len(text) > 4000:
        text = text[:4000] + "\n\n<i>[Сообщение обрезано из-за ограничений Telegram...]</i>"

    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        logger.info(f"Sending standard HTML message to chat {chat_id}")
        response = httpx.post(url, json=payload, timeout=20)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error in send_html_message: {e}")
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

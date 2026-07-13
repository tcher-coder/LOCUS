import os
import re
import json
import yaml
import logging
from datetime import datetime

from telegram_out import send_markdown_text

logger = logging.getLogger("locus.archive")

# Каталог данных: в Docker задаётся LOCUS_DATA_DIR=/app/data (bind-mount, переживает пересборку)
_DATA_DIR = os.getenv("LOCUS_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_DATA_DIR, exist_ok=True)
INDEX_FILE = os.path.join(_DATA_DIR, "archive_index.json")

def load_archive_index() -> dict:
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading archive index: {e}")
    return {}

def save_archive_index(index: dict):
    try:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving archive index: {e}")

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

def format_hashtag(tag: str) -> str:
    """Formats a tag string into a valid Telegram hashtag."""
    tag = tag.strip().lower()
    tag = re.sub(r'[\s\-\.\/]+', '_', tag)
    tag = re.sub(r'[^\w]', '', tag, flags=re.UNICODE)
    if not tag:
        return ""
    return "#" + tag

def build_channel_post(abs_path: str) -> str:
    """
    Готовит Markdown rich-поста для архивного канала из raw-конспекта:
    без front-matter и оглавления (TL;DR остаётся), с хэштегами в конце.
    Файлы в канал не отправляются — .md от ботов Telegram открывает криво
    (расширения .md нет в таблице MIME-типов Bot API).
    """
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()

    meta_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    meta = {}
    if meta_match:
        try:
            meta = yaml.safe_load(meta_match.group(1)) or {}
        except Exception:
            meta = {}

    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    body = re.sub(
        r'^#{1,4}\s*(Оглавление|Содержание).*?(?=^#{1,4}\s|\Z)',
        '', body, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    # Вики-ссылки [[Имя]] в канале не кликабельны — показываем жирным
    body = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'**\1**', body).strip()

    hashtags = [format_hashtag(str(meta.get("type", "text")))]
    tags = meta.get("tags", [])
    if isinstance(tags, list):
        for t in tags:
            formatted = format_hashtag(str(t))
            if formatted:
                hashtags.append(formatted)
    hashtag_line = " ".join(filter(None, hashtags))

    if hashtag_line:
        body = f"{body}\n\n{hashtag_line}"
    return body

def archive_post(doc_rel_path: str, bot_token: str, channel_id: str, vault_dir: str) -> bool:
    """
    Публикует конспект в архивный канал rich-постом (выжимка + хэштеги).
    Updates archive_index.json.
    """
    if not channel_id:
        logger.warning("ARCHIVE_CHANNEL_ID is not configured. Skipping archive posting.")
        return False

    abs_path = os.path.join(vault_dir, doc_rel_path)
    if not os.path.exists(abs_path):
        logger.error(f"Archive file not found: {abs_path}")
        return False

    try:
        post_md = build_channel_post(abs_path)
        filename = os.path.basename(doc_rel_path)

        logger.info(f"Posting rich post for {filename} to archive channel {channel_id}")
        if not send_markdown_text(channel_id, bot_token, post_md):
            logger.error("Failed to post rich message to archive channel.")
            return False

        index = load_archive_index()
        index[filename] = {"posted_at": datetime.now().isoformat()}
        save_archive_index(index)
        return True

    except Exception as e:
        logger.exception("Error in archive_post")
        return False

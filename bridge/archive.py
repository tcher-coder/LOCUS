import os
import re
import json
import yaml
import httpx
import logging
from datetime import datetime

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

def archive_post(doc_rel_path: str, summary: str, bot_token: str, channel_id: str, vault_dir: str) -> bool:
    """
    Posts the document file to the Telegram archive channel.
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
        # 1. Parse front-matter
        meta = parse_yaml_front_matter(abs_path)
        doc_type = meta.get("type", "text")
        tags = meta.get("tags", [])

        # Build hashtags
        hashtags = [format_hashtag(doc_type)]
        if isinstance(tags, list):
            for t in tags:
                formatted = format_hashtag(str(t))
                if formatted:
                    hashtags.append(formatted)
        
        hashtag_line = " ".join(filter(None, hashtags))
        
        # 2. Build caption (limit is 1024 chars for sendDocument)
        caption_suffix = f"\n\n{hashtag_line}"
        max_summary_len = 1024 - len(caption_suffix)
        
        clean_summary = summary.strip()
        if len(clean_summary) + len(caption_suffix) > 1024:
            clean_summary = clean_summary[:max_summary_len - 3] + "..."
            
        caption = f"{clean_summary}{caption_suffix}"

        # 3. Check file size
        file_size = os.path.getsize(abs_path)
        if file_size > 50 * 1024 * 1024:
            logger.error(f"File {abs_path} exceeds Telegram's 50MB limit ({file_size} bytes). Skipping.")
            return False

        # 4. Send to Telegram
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        filename = os.path.basename(doc_rel_path)
        
        logger.info(f"Posting {filename} to archive channel {channel_id}")
        with open(abs_path, "rb") as f:
            content = f.read()
        # Явный MIME text/markdown — без него Telegram считает файл бинарным
        # (octet-stream) и ломает предпросмотр/кодировку.
        mime = "text/markdown" if filename.lower().endswith(".md") else None
        files = {"document": (filename, content, mime) if mime else (filename, content)}
        data = {"chat_id": channel_id, "caption": caption}
        response = httpx.post(url, data=data, files=files, timeout=30)

        if response.status_code == 200:
            logger.info("Successfully posted to archive channel.")
            msg_id = response.json()["result"]["message_id"]
            
            # Update index
            index = load_archive_index()
            index[filename] = {
                "message_id": msg_id,
                "posted_at": datetime.now().isoformat()
            }
            save_archive_index(index)
            return True
        else:
            logger.error(f"Failed to post to archive (status {response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.exception("Error in archive_post")
        return False

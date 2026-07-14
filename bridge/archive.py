import os
import re
import json
import yaml
import logging
from datetime import datetime

from telegram_out import send_markdown_text, build_post_parts

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

def build_channel_post(abs_path: str, gallery_captions: list = None) -> list:
    """
    Готовит rich-пост(ы) для архивного канала из raw-конспекта: суть сверху,
    разделы аккордеоном (<details>). Длинный конспект делится на части «— Ч.N».
    Хэштеги не добавляются (решение владельца, 2026-07).
    Файлы в канал не отправляются — .md от ботов Telegram открывает криво
    (расширения .md нет в таблице MIME-типов Bot API).
    gallery_captions — подписи кадров для свайп-галереи (первая часть поста);
    сама заливка/переиспользование фото — забота вызывающего кода.
    """
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    return build_post_parts(content, gallery_captions=gallery_captions)

def archive_post(doc_rel_path: str, bot_token: str, channel_id: str, vault_dir: str,
                  gallery_file_ids: list = None) -> bool:
    """
    Публикует конспект в архивный канал rich-постом (выжимка + хэштеги).
    Updates archive_index.json.

    gallery_file_ids — file_id кадров, уже загруженных при отправке в чат
    владельца (bridge/main.py): если переданы, первая часть поста уходит с
    той же свайп-галереей, но БЕЗ повторной заливки файлов (чистый JSON,
    media через file_id). Подписи берём из front-matter того же raw-файла —
    порядок file_id должен соответствовать порядку gallery в front-matter.
    """
    if not channel_id:
        logger.warning("ARCHIVE_CHANNEL_ID is not configured. Skipping archive posting.")
        return False

    abs_path = os.path.join(vault_dir, doc_rel_path)
    if not os.path.exists(abs_path):
        logger.error(f"Archive file not found: {abs_path}")
        return False

    try:
        gallery = None
        gallery_captions = None
        if gallery_file_ids:
            meta = parse_yaml_front_matter(abs_path)
            raw_items = meta.get("gallery") or []
            gallery_captions = []
            for i in range(len(gallery_file_ids)):
                item = raw_items[i] if i < len(raw_items) and isinstance(raw_items[i], dict) else {}
                gallery_captions.append(item.get("caption") or "")
            gallery = [{"id": f"shot{i + 1}", "file_id": fid} for i, fid in enumerate(gallery_file_ids)]

        post_parts = build_channel_post(abs_path, gallery_captions=gallery_captions)
        filename = os.path.basename(doc_rel_path)

        logger.info(f"Posting rich post ({len(post_parts)} part(s)) for {filename} to archive channel {channel_id}")
        for idx, part in enumerate(post_parts):
            part_gallery = gallery if (idx == 0 and gallery) else None
            if not send_markdown_text(channel_id, bot_token, part, gallery=part_gallery):
                logger.error("Failed to post rich message to archive channel.")
                return False

        index = load_archive_index()
        index[filename] = {"posted_at": datetime.now().isoformat()}
        save_archive_index(index)
        return True

    except Exception as e:
        logger.exception("Error in archive_post")
        return False

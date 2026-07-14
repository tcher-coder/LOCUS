import os
import re
import json
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

# Раздел «Ключевые идеи»: маркеры вместо цифр, своя иконка
KEY_IDEAS_RE = re.compile(r'ключев', re.IGNORECASE)
SOURCES_RE = re.compile(r'источник', re.IGNORECASE)

def _summary_icon(head_clean: str) -> str:
    """
    Иконка для заголовка плашки. Тематические эмодзи ставит агент прямо
    в заголовках разделов (правило стиля); здесь — только дефолты для
    стандартных секций, если агент иконку не поставил.
    """
    if not re.match(r'[\w«"„(]', head_clean):
        return ""  # уже начинается с эмодзи/символа
    if KEY_IDEAS_RE.search(head_clean):
        return "💡 "
    if SOURCES_RE.search(head_clean):
        return "🔗 "
    return ""

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
            icon = _summary_icon(head_clean)
            res.append(f"<details><summary><b>{icon}{head_clean}</b></summary>\n\n{content}\n\n</details>")
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

# Свайп-галерея кадров видео (+frames): агент сам решает, сколько кадров
# брать (1..10) — по реальной визуальной ценности материала, а не для галочки.
# Верхняя граница нужна как страховка от раздувания multipart-заливки.
GALLERY_MAX = 10

def build_gallery_md(captions: list) -> str:
    """
    Блок свайп-галереи <tg-slideshow> с shot1..shotN. Пустая строка сразу после
    открывающего тега и перед закрывающим — обязательна, без неё Telegram не
    распознаёт слайд-шоу (проверено смоук-тестом на проде). Кавычки в подписи
    экранируем заменой на одинарные — двойная кавычка сломала бы title-атрибут.
    """
    lines = ["<tg-slideshow>", ""]
    for i, caption in enumerate(captions, 1):
        safe_caption = (caption or "").replace('"', "'")
        lines.append(f'![](tg://photo?id=shot{i} "{safe_caption}")')
    lines.append("")
    lines.append("</tg-slideshow>")
    return "\n".join(lines)

def build_post_parts(content: str, max_len: int = POST_PART_MAX_LEN, gallery_captions: list = None) -> list:
    """
    Из содержимого raw-конспекта (с front-matter) готовит Telegram-пост:
    шапка с названием капсом в дивайдерах, суть цитатой (TL;DR без ярлыка),
    ниже — разделы аккордеоном, дивайдер в конце.
    Длинный пост делится на части по границам плашек: каждая часть получает
    ту же шапку с пометкой «— Ч.N». Возвращает список Markdown-постов.
    Если передан gallery_captions — свайп-галерея встаёт САМЫМ первым блоком
    parts[0], ДО шапки с названием (только в первую часть — в «Ч.2» кадрам
    делать нечего, они уже показаны).
    """
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
    # Убираем раздел "Оглавление"/"Содержание" целиком ([^\w\s]* — допуск
    # на тематическое эмодзи, которое агент ставит в заголовках)
    body = re.sub(
        r'^#{1,4}\s*[^\w\s#]*\s*(Оглавление|Содержание)\b.*?(?=^#{1,4}\s|\Z)',
        '', body, flags=re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    # Заголовок TL;DR убираем, сам текст сути остаётся открытым сверху
    body = re.sub(r'^#{1,4}\s*[^\w\s#]*\s*TL;?DR\s*:?\s*$\n?', '', body,
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

    # Дивайдер между преамбулой (TL;DR) и аккордеоном: явная граница «суть/детали»
    if len(blocks) > 1 and not blocks[0].startswith("<details"):
        blocks.insert(1, "---")

    # Блок галереи считаем заранее — его длину нужно вычесть из бюджета
    # только первой группы (галерея уходит исключительно в parts[0]).
    gallery_md = build_gallery_md(gallery_captions) if gallery_captions else ""
    gallery_budget = len(gallery_md) + 2 if gallery_md else 0  # +2 на "\n\n" перед шапкой

    # Группируем блоки в части: плашки не режем, преамбула — всегда в первой
    groups, current, current_len = [], [], 0
    header_len = len(_title_header(title, 9))
    for block in blocks:
        # Запас под галерею действует, пока копим самую первую группу
        # (groups ещё пуст) — остальные части галереи не несут.
        extra = gallery_budget if not groups else 0
        if current and current_len + len(block) > max_len - header_len - extra:
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
        if i == 1 and gallery_md:
            chunk = gallery_md + "\n\n" + chunk
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

def send_markdown_text(chat_id: int, bot_token: str, md_text: str, sent_ids: list = None,
                        gallery: list = None, out_file_ids: list = None) -> bool:
    """
    Отправляет Markdown-текст в чат rich-сообщениями (HTML-фолбэка нет —
    решение владельца, 2026-07). Текст длиннее лимита rich-сообщения
    разбивается на несколько сообщений по границам блоков.
    В sent_ids (если передан список) складываются message_id всех отправленных
    сообщений — для привязки реплай-сессий.
    gallery применяется ТОЛЬКО к первому чанку — сама галерея (build_post_parts)
    уже вшита в его markdown, здесь просто нужно приложить файлы/file_id к тому
    же HTTP-запросу; во второй и последующие чанки её передавать не нужно.
    """
    all_ok = True
    for i, chunk in enumerate(split_markdown_chunks(md_text)):
        chunk_gallery = gallery if (gallery and i == 0) else None
        chunk_out_ids = out_file_ids if i == 0 else None
        mid = send_rich_message(chat_id, bot_token, chunk, gallery=chunk_gallery, out_file_ids=chunk_out_ids)
        if mid:
            if sent_ids is not None and isinstance(mid, int):
                sent_ids.append(mid)
        else:
            all_ok = False
    return all_ok

def _largest_photo_size(photo_node) -> dict:
    """
    Внутри ОДНОГО блока type:"photo" рекурсивно находит все объекты-размеры
    (PhotoSize — есть file_id/file_unique_id/width/height) и возвращает
    крупнейший (по file_size, а если его нет — по width*height).
    """
    sizes = []

    def collect(n):
        if isinstance(n, dict):
            if "file_id" in n and "width" in n and "height" in n:
                sizes.append(n)
            for v in n.values():
                collect(v)
        elif isinstance(n, list):
            for v in n:
                collect(v)

    collect(photo_node)
    if not sizes:
        return {}
    return max(sizes, key=lambda s: s.get("file_size", s.get("width", 0) * s.get("height", 0)))

def _collect_photo_sizes(node, out: list):
    """
    Рекурсивно обходит произвольный JSON-ответ Bot API и собирает file_id фото
    слайд-шоу, по одному на КАЖДЫЙ блок {"type": "photo"}, в порядке появления
    этих блоков (это и есть порядок shot1..shotN в галерее).

    ГРАБЛИ (уже наступали на проде, повтор даёт дубликаты в канале): у Telegram
    каждое фото приходит МАССИВОМ PhotoSize, и у КАЖДОГО размера свой
    собственный file_id И свой собственный file_unique_id — они не общие для
    всех размеров одной картинки. Поэтому группировать по file_unique_id
    НЕЛЬЗЯ: так каждый размер считается отдельным "фото", и список получается
    длиннее реального числа кадров с перекосом (все размеры фото №1, потом все
    размеры фото №2, ...). extract_gallery_file_ids(...)[:len(gallery)] тогда
    отрезает первые N элементов этого перекошенного списка — то есть все
    размеры первых одной-двух картинок — и в канал улетают дубликаты.
    Правильная единица фото — это сам блок type:"photo" из слайд-шоу; внутри
    него нужно взять один, самый крупный размер (см. _largest_photo_size).
    """
    if isinstance(node, dict):
        if node.get("type") == "photo":
            big = _largest_photo_size(node)
            if big:
                out.append(big["file_id"])
            # Внутрь уже отправленного фото-блока не спускаемся — иначе
            # найдём его же PhotoSize ещё раз через общий обход.
            return
        for v in node.values():
            _collect_photo_sizes(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_photo_sizes(v, out)

def extract_gallery_file_ids(response_json: dict) -> list:
    """file_id всех фото слайд-шоу из ответа sendRichMessage, по одному на
    фото (не на PhotoSize!), в порядке появления фото-блоков."""
    out = []
    _collect_photo_sizes(response_json, out)
    return out

def send_rich_message(chat_id: int, bot_token: str, md_content: str,
                       gallery: list = None, out_file_ids: list = None):
    """
    Sends a Rich Message to Telegram Bot API 10.1 using raw HTTP.
    InputRichMessage принимает Markdown-строку напрямую (поле `markdown`) —
    Telegram сам парсит заголовки, списки, таблицы, цитаты и код.

    gallery — список dict вида {"id": "shot1", "path": "/abs/x.jpg"} (локальный
    файл — уйдёт multipart с attach://) или {"id": "shot1", "file_id": "AgAC…"}
    (переиспользование уже загруженного фото — чистый JSON, без повторной
    заливки). Если в списке есть хоть один элемент с "path" — весь запрос идёт
    multipart (Bot API не умеет мешать attach:// с обычными полями в JSON).
    Если gallery пуст/None — путь ровно как раньше, чистый JSON (99% сообщений:
    статусы, /ask, посты без кадров) — не трогаем, чтобы не сломать.
    out_file_ids (если передан список) получит file_id отправленных фото —
    порядок соответствует shot1..shotN, пригодится, чтобы канал не перезаливал
    те же кадры повторно.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"
    has_local = bool(gallery) and any("path" in g for g in gallery)
    try:
        if not gallery:
            payload = {
                "chat_id": chat_id,
                "rich_message": {"markdown": md_content}
            }
            logger.info(f"Sending rich message to chat {chat_id}")
            response = httpx.post(url, json=payload, timeout=20)
        elif has_local:
            media = [
                {"id": g["id"], "media": {"type": "photo", "media": f"attach://{g['id']}"}}
                for g in gallery
            ]
            rich_obj = {"markdown": md_content, "media": media}
            # multipart: rich_message едет строкой (JSON внутри form-data), картинки — отдельными частями
            data = {"chat_id": chat_id, "rich_message": json.dumps(rich_obj, ensure_ascii=False)}
            files = {}
            opened = []
            try:
                for g in gallery:
                    f = open(g["path"], "rb")
                    opened.append(f)
                    files[g["id"]] = (os.path.basename(g["path"]), f, "image/jpeg")
                logger.info(f"Sending rich message with gallery ({len(gallery)} local photo(s)) to chat {chat_id}")
                response = httpx.post(url, data=data, files=files, timeout=60)
            finally:
                for f in opened:
                    f.close()
        else:
            media = [
                {"id": g["id"], "media": {"type": "photo", "media": g["file_id"]}}
                for g in gallery
            ]
            rich_obj = {"markdown": md_content, "media": media}
            payload = {"chat_id": chat_id, "rich_message": rich_obj}
            logger.info(f"Sending rich message with gallery ({len(gallery)} reused file_id) to chat {chat_id}")
            response = httpx.post(url, json=payload, timeout=20)

        if response.status_code == 200:
            logger.info("Rich message sent successfully.")
            try:
                body = response.json()
                if out_file_ids is not None and gallery:
                    found = extract_gallery_file_ids(body)
                    if len(found) != len(gallery):
                        logger.warning(
                            f"extract_gallery_file_ids: нашли {len(found)} фото-блоков, "
                            f"а отправляли {len(gallery)} — Bot API вернул не то, что ожидалось. "
                            f"Срез [:len(gallery)] — не более чем страховка от IndexError."
                        )
                    # Срез — страховка на случай расхождения количества (см. warning выше),
                    # а не часть нормальной логики: в норме len(found) == len(gallery).
                    out_file_ids.extend(found[:len(gallery)])
                # message_id — истинное значение; True как фолбэк, если тела нет
                return body["result"]["message_id"]
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

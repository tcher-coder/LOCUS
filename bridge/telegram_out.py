import os
import re
import httpx
import logging

logger = logging.getLogger("locus.telegram_out")

def parse_inline_markdown(text: str):
    """
    Parses bold, italic, code, and links in inline markdown.
    Returns a RichText structure: string, dict, or list of RichText.
    """
    if not text:
        return ""

    # Tokens will be a list of strings and dictionaries
    tokens = []
    
    # regex for link: [text](url)
    # regex for bold: **text** or __text__
    # regex for italic: *text* or _text_
    # regex for code: `text`
    pattern = re.compile(
        r'(?P<bold>\*\*(.*?)\*\*|__(.*?)__)|'
        r'(?P<italic>\*(.*?)\*|_(.*?)_)|'
        r'(?P<code>`(.*?)`)|'
        r'(?P<link>\[(.*?)\]\((.*?)\))'
    )
    
    last_idx = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        # Add plain text before match
        if start > last_idx:
            tokens.append(text[last_idx:start])
            
        group_dict = match.groupdict()
        if group_dict.get("bold"):
            val = match.group(2) if match.group(2) is not None else match.group(3)
            tokens.append({"type": "bold", "text": val})
        elif group_dict.get("italic"):
            val = match.group(5) if match.group(5) is not None else match.group(6)
            tokens.append({"type": "italic", "text": val})
        elif group_dict.get("code"):
            val = match.group(8)
            tokens.append({"type": "code", "text": val})
        elif group_dict.get("link"):
            link_text = match.group(10)
            link_url = match.group(11)
            tokens.append({"type": "url", "text": link_text, "url": link_url})
            
        last_idx = end
        
    if last_idx < len(text):
        tokens.append(text[last_idx:])
        
    # Simplify structure
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0]
    return tokens

def markdown_to_rich_message(md_text: str) -> dict:
    """
    Parses Markdown text into Telegram Rich Blocks structure.
    Supports headings, paragraphs, lists, preformatted blocks, blockquotes, dividers, and tables.
    """
    blocks = []
    lines = md_text.splitlines()
    i = 0
    n = len(lines)
    
    while i < n:
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
            
        # 1. Divider
        if line in ["---", "***", "___"]:
            blocks.append({"type": "divider"})
            i += 1
            continue
            
        # 2. Headings
        if line.startswith("#"):
            level_match = re.match(r'^(#{1,6})\s+(.*)$', line)
            if level_match:
                # level = len(level_match.group(1))
                heading_text = level_match.group(2)
                blocks.append({
                    "type": "section_heading",
                    "text": parse_inline_markdown(heading_text)
                })
                i += 1
                continue
                
        # 3. Blockquotes
        if line.startswith(">"):
            quote_lines = []
            while i < n and (lines[i].strip().startswith(">") or not lines[i].strip()):
                l = lines[i].strip()
                if l.startswith(">"):
                    quote_lines.append(l[1:].strip())
                else:
                    quote_lines.append("")
                i += 1
            blocks.append({
                "type": "block_quotation",
                "text": parse_inline_markdown("\n".join(quote_lines))
            })
            continue
            
        # 4. Preformatted (Code blocks)
        if line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing backticks
            
            blocks.append({
                "type": "preformatted",
                "text": "\n".join(code_lines),
                "language": lang if lang else "text"
            })
            continue
            
        # 5. Tables
        if line.startswith("|") and i + 1 < n and lines[i+1].strip().startswith("|") and "-" in lines[i+1]:
            # Parse table
            headers = [cell.strip() for cell in line.split("|")[1:-1]]
            i += 2  # Skip header and separator lines
            
            rows = []
            # Add header row
            header_cells = [{"text": parse_inline_markdown(h)} for h in headers]
            rows.append(header_cells)
            
            while i < n and lines[i].strip().startswith("|"):
                row_cells = [cell.strip() for cell in lines[i].split("|")[1:-1]]
                rows.append([{"text": parse_inline_markdown(c)} for c in row_cells])
                i += 1
                
            blocks.append({
                "type": "table",
                "rows": rows
            })
            continue
            
        # 6. Lists (bullet or numbered)
        if line.startswith(("-", "*", "+")) or re.match(r'^\d+\.\s', line):
            list_items = []
            while i < n:
                l = lines[i].strip()
                if not l:
                    # Allow one blank line within list
                    if i + 1 < n and (lines[i+1].strip().startswith(("-", "*", "+")) or re.match(r'^\d+\.\s', lines[i+1].strip())):
                        i += 1
                        continue
                    else:
                        break
                
                list_match = re.match(r'^([-\*\+])\s+(.*)$', l)
                num_match = re.match(r'^(\d+)\.\s+(.*)$', l)
                
                if list_match:
                    list_items.append({"text": parse_inline_markdown(list_match.group(2))})
                    i += 1
                elif num_match:
                    list_items.append({"text": parse_inline_markdown(num_match.group(2))})
                    i += 1
                else:
                    # Append to previous item if it doesn't start with list marker
                    if list_items:
                        prev_text = list_items[-1]["text"]
                        if isinstance(prev_text, str):
                            list_items[-1]["text"] = prev_text + "\n" + l
                        elif isinstance(prev_text, list):
                            list_items[-1]["text"].append("\n" + l)
                        else:
                            list_items[-1]["text"] = [prev_text, "\n" + l]
                        i += 1
                    else:
                        break
            
            blocks.append({
                "type": "list",
                "items": list_items
            })
            continue
            
        # 7. Standard Paragraph
        # Collect consecutive non-empty lines as a single paragraph
        para_lines = []
        while i < n and lines[i].strip() and not lines[i].strip().startswith(("#", ">", "```", "|", "-", "*", "+")) and not re.match(r'^\d+\.\s', lines[i].strip()):
            para_lines.append(lines[i].strip())
            i += 1
            
        blocks.append({
            "type": "paragraph",
            "text": parse_inline_markdown("\n".join(para_lines))
        })
        
    return {"blocks": blocks}

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

def send_rich_message(chat_id: int, bot_token: str, md_content: str) -> bool:
    """
    Sends a Rich Message to Telegram Bot API 10.1 using raw HTTP.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendRichMessage"
    try:
        rich_msg = markdown_to_rich_message(md_content)
        payload = {
            "chat_id": chat_id,
            "rich_message": rich_msg
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
            files = {"document": (filename, f)}
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

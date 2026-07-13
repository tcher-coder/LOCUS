import os
import sys
import logging
import asyncio
from typing import AsyncIterator, Dict, Any

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage
)

logger = logging.getLogger("locus.agent")

async def run_locus_agent(
    prompt: str,
    vault_path: str,
    effort: str = "low",
    groq_api_key: str = None,
    resume_session_id: str = None
) -> AsyncIterator[Dict[str, Any]]:
    """
    Runs the Claude Agent SDK with the specified prompt, cwd, and effort.
    Yields events:
      - {"type": "status", "status": "started" | "reading" | "conspecting" | "updating_wiki" | "finished"}
      - {"type": "chunk", "text": "..."}
      - {"type": "session_id", "session_id": "..."}
      - {"type": "result", "text": "...", "success": True|False, "error": "...", "session_id": "..."}
    """
    # Propagate GROQ_API_KEY to os.environ for Whisper fallback in the /watch skill
    if groq_api_key:
        os.environ["GROQ_API_KEY"] = groq_api_key

    # Configure options
    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        allowed_tools=["Read", "Write", "Edit", "Bash", "WebFetch", "WebSearch", "Glob", "Grep", "Skill"],
        permission_mode="bypassPermissions", # Run without manual confirmation prompts
        # ВАЖНО: без setting_sources SDK работает герметично и НЕ подхватывает
        # ни глобальный скилл /watch (user), ни vault/AGENTS.md (project).
        setting_sources=["user", "project"],
        cwd=vault_path,
        max_turns=80,  # запас на краулинг до 20 страниц
        effort=effort,
        resume=resume_session_id
    )

    logger.info(f"Starting agent session in {vault_path} with effort={effort}, resume={resume_session_id}")
    yield {"type": "status", "status": "started"}

    full_response_text = ""
    current_status = "started"
    captured_session_id = resume_session_id

    try:
        # Run query
        async for message in query(prompt=prompt, options=options):
            # Capture session ID if present
            if hasattr(message, "session_id") and message.session_id:
                if message.session_id != captured_session_id:
                    captured_session_id = message.session_id
                    yield {"type": "session_id", "session_id": captured_session_id}

            # 1. Handle assistant messages
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    # Text chunks
                    if isinstance(block, TextBlock):
                        # Блоки — самостоятельные фрагменты; без переноса между ними
                        # маркер RESULT: может слипнуться с предыдущим текстом
                        # и не пройти ^-регэксп парсера маркеров в main.py
                        if full_response_text and not full_response_text.endswith("\n"):
                            full_response_text += "\n"
                        full_response_text += block.text
                        yield {"type": "chunk", "text": block.text}
                    
                    # Detect stage from tool use
                    elif isinstance(block, ToolUseBlock):
                        tool_name = block.name
                        tool_input = block.input or {}
                        
                        # Determine stage based on tool name and file paths
                        new_status = None
                        if tool_name in ["WebFetch", "WebSearch"]:
                            new_status = "reading"
                        elif tool_name == "Bash":
                            cmd = tool_input.get("command", "")
                            if "watch" in cmd or "yt-dlp" in cmd or "ffmpeg" in cmd:
                                new_status = "reading"
                        elif tool_name in ["Write", "Edit"]:
                            path = tool_input.get("path", "")
                            if "raw/" in path:
                                new_status = "conspecting"
                            elif "wiki/" in path or "log.md" in path or "index.md" in path:
                                new_status = "updating_wiki"
                                
                        if new_status and new_status != current_status:
                            current_status = new_status
                            logger.info(f"Agent stage updated: {current_status}")
                            yield {"type": "status", "status": current_status}
            
            # 2. Handle final ResultMessage
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    # У ResultMessage нет поля .errors — текст ошибки лежит в .result
                    error_msg = getattr(message, "result", None) or "Unknown SDK error"
                    logger.error(f"Agent finished with error: {error_msg}")
                    yield {
                        "type": "result",
                        "text": full_response_text,
                        "success": False,
                        "error": error_msg,
                        "session_id": captured_session_id
                    }
                    return
                else:
                    logger.info("Agent completed successfully.")
                    
        # Successfully finished generator
        yield {"type": "status", "status": "finished"}
        yield {
            "type": "result",
            "text": full_response_text,
            "success": True,
            "error": None,
            "session_id": captured_session_id
        }

    except Exception as e:
        logger.exception("Exception in run_locus_agent")
        yield {
            "type": "result",
            "text": full_response_text,
            "success": False,
            "error": str(e),
            "session_id": captured_session_id
        }

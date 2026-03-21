"""Read session JSONL files for conversation turns and token usage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .scanner import is_noise_message

logger = logging.getLogger(__name__)

_ASSISTANT_TEXT_TRUNCATE = 200


def read_session_detail(
    jsonl_path: Path,
    max_turns: int = 10,
) -> dict[str, Any]:
    """Read a session JSONL and extract conversation turns + token totals.

    Returns a dict with:
    - ``turns``: list of ``{"role": "user"|"assistant", "text": str}``
    - ``total_input_tokens``: int
    - ``total_output_tokens``: int
    """
    result: dict[str, Any] = {
        "turns": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }
    try:
        fh = jsonl_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return result

    turns_collected = 0
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            msg_type = obj.get("type")
            message = obj.get("message", {})
            if not isinstance(message, dict):
                continue

            # Sum token usage from all assistant messages
            if msg_type == "assistant":
                usage = message.get("usage", {})
                if isinstance(usage, dict):
                    result["total_input_tokens"] += usage.get("input_tokens", 0) or 0
                    result["total_output_tokens"] += usage.get("output_tokens", 0) or 0

            # Collect conversation turns (up to max_turns)
            if turns_collected >= max_turns:
                continue

            if msg_type == "user":
                text = _extract_user_text(message.get("content", ""))
                if text:
                    if is_noise_message(text):
                        continue
                    result["turns"].append({"role": "user", "text": text})
                    turns_collected += 1
            elif msg_type == "assistant":
                text = _extract_assistant_text(message.get("content", ""))
                if text:
                    if len(text) > _ASSISTANT_TEXT_TRUNCATE:
                        text = text[:_ASSISTANT_TEXT_TRUNCATE] + "..."
                    result["turns"].append({"role": "assistant", "text": text})
                    turns_collected += 1

    return result


def _extract_user_text(content: Any) -> str:
    """Extract text from user message content (string or parts list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                # Accept dicts with "type":"text" or plain {"text": "..."} dicts
                if p.get("type", "text") == "text":
                    parts.append(p.get("text", ""))
            elif isinstance(p, str):
                parts.append(p)
        return " ".join(t for t in parts if t)
    return ""


def _extract_assistant_text(content: Any) -> str:
    """Extract text from assistant message content, skipping thinking/tool_use."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return " ".join(t for t in parts if t)
    return ""

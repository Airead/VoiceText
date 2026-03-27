"""Dictionary plugin — EN↔ZH lookup via Youdao."""

from __future__ import annotations

import asyncio
import re
from html import escape as _esc

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _detect_direction(query: str) -> str:
    """Return Youdao direction string based on query characters."""
    if _CJK_RE.search(query):
        return "zh2en"
    return "en2zh-CHS"


def setup(wz) -> None:
    """Register the dictionary chooser source."""
    from .render import render_definition
    from .youdao import lookup, suggest

    def _make_preview(word: str, direction: str):
        """Return a lazy callable for the preview panel."""
        def _load():
            data = lookup(word, direction)
            if not data:
                return {
                    "type": "html",
                    "content": f'<div style="color:var(--secondary);'
                    f'text-align:center;padding:40px">'
                    f"Failed to load definition for <b>{_esc(word)}</b></div>",
                }
            return {"type": "html", "content": render_definition(data, word)}
        return _load

    @wz.chooser.source(
        "dictionary",
        prefix="d",
        priority=5,
        description="Youdao Dictionary (EN↔ZH)",
        show_preview=True,
        action_hints={"enter": "Dismiss"},
        search_timeout=5.0,
        debounce_delay=0.2,
    )
    async def search(query: str) -> list:
        if not query.strip():
            return []

        direction = _detect_direction(query)
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, suggest, query)

        return [
            {
                "title": entry["word"],
                "subtitle": entry.get("explain", ""),
                "preview": _make_preview(entry["word"], direction),
            }
            for entry in results
        ]

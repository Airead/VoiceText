"""Clipboard history data source for the Chooser.

Provides search over clipboard history entries recorded by
ClipboardMonitor. Activated via ">cb" prefix or Tab key switching.
"""

from __future__ import annotations

import logging
import time
from typing import List

from voicetext.scripting.clipboard_monitor import ClipboardMonitor
from voicetext.scripting.sources import ChooserItem, ChooserSource

logger = logging.getLogger(__name__)


def _format_time_ago(timestamp: float) -> str:
    """Format a timestamp as a human-readable relative time."""
    delta = time.time() - timestamp
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = int(delta / 60)
        return f"{minutes}m ago"
    if delta < 86400:
        hours = int(delta / 3600)
        return f"{hours}h ago"
    days = int(delta / 86400)
    return f"{days}d ago"


def _paste_text(text: str) -> None:
    """Write text to clipboard and simulate Cmd+V to paste at cursor."""
    try:
        from voicetext.input import _set_pasteboard_concealed

        import subprocess
        import time as _time

        _set_pasteboard_concealed(text)
        _time.sleep(0.05)
        subprocess.run(
            [
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            capture_output=True, timeout=5,
        )
    except Exception:
        logger.exception("Failed to paste clipboard text")


def _copy_to_clipboard(text: str) -> None:
    """Write text to the system clipboard (without pasting).

    Uses concealed marker so the clipboard monitor does not re-record it,
    but moves the entry to the top of history for freshness.
    """
    try:
        from voicetext.input import _set_pasteboard_concealed

        _set_pasteboard_concealed(text)
    except Exception:
        logger.exception("Failed to copy to clipboard")


class ClipboardSource:
    """Clipboard history search data source.

    Uses a ClipboardMonitor to access recorded entries.
    Supports substring filtering and pastes the selected entry on execute.
    """

    def __init__(self, monitor: ClipboardMonitor) -> None:
        self._monitor = monitor

    def search(self, query: str) -> List[ChooserItem]:
        """Search clipboard history entries."""
        entries = self._monitor.entries

        if not entries:
            return []

        q = query.strip().lower()
        results = []

        for entry in entries:
            if q and q not in entry.text.lower():
                continue

            # Truncate long text for display
            display = entry.text.replace("\n", " ").strip()
            if len(display) > 80:
                display = display[:77] + "..."

            time_ago = _format_time_ago(entry.timestamp)
            subtitle = entry.source_app if entry.source_app else ""

            text = entry.text  # Capture for lambda
            monitor = self._monitor

            def _do_paste(t=text, m=monitor):
                m.promote(t)
                _paste_text(t)

            def _do_copy(t=text, m=monitor):
                m.promote(t)
                _copy_to_clipboard(t)

            results.append(
                ChooserItem(
                    title=display,
                    subtitle=f"{subtitle}  {time_ago}".strip() if subtitle else time_ago,
                    action=_do_paste,
                    secondary_action=_do_copy,
                )
            )

        return results

    def as_chooser_source(self) -> ChooserSource:
        """Return a ChooserSource wrapping this ClipboardSource."""
        return ChooserSource(
            name="clipboard",
            prefix=">cb",
            search=self.search,
            priority=5,
        )

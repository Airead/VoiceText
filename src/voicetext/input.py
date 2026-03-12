"""Text injection into the active macOS application."""

from __future__ import annotations

import logging
import subprocess
import threading
import time

from AppKit import NSPasteboard, NSPasteboardTypeString, NSString

logger = logging.getLogger(__name__)


def get_clipboard_text() -> str | None:
    """Read the current plain-text content from the system clipboard."""
    return _get_pasteboard_string()


def set_clipboard_text(text: str) -> None:
    """Write text to the system clipboard (visible in clipboard history)."""
    _set_pasteboard_string(text)


def type_text(text: str, append_newline: bool = False, method: str = "auto") -> None:
    """Type text into the currently focused text field on macOS.

    Methods:
        clipboard: pbcopy + Cmd+V (fast, reliable)
        applescript: AppleScript keystroke (good Unicode support)
        auto: try clipboard first, fall back to applescript
    """
    if not text:
        return

    payload = text + ("\n" if append_newline else "")

    method = (method or "auto").lower()
    if method == "clipboard":
        order = ["clipboard"]
    elif method == "applescript":
        order = ["applescript"]
    else:
        order = ["clipboard", "applescript"]

    for mode in order:
        if mode == "clipboard" and _type_via_clipboard(payload):
            logger.info("Text injected via clipboard: %s", payload[:50])
            return
        if mode == "applescript" and _type_via_applescript(payload):
            logger.info("Text injected via applescript: %s", payload[:50])
            return

    logger.error("All text injection methods failed")


def _get_pasteboard_string() -> str | None:
    """Read the current plain-text content from the system pasteboard."""
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSPasteboardTypeString)


def _set_pasteboard_concealed(text: str) -> bool:
    """Write *text* to the pasteboard with concealed/transient markers.

    Clipboard history managers (Paste, Maccy, Raycast, etc.) honour
    ``org.nspasteboard.ConcealedType`` and ``com.nspasteboard.TransientType``
    and will skip entries that carry these types.
    """
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    ns_str = NSString.stringWithString_(text)
    ok = pb.setString_forType_(ns_str, NSPasteboardTypeString)
    if not ok:
        return False
    # Marker types – the value is irrelevant; their presence is the signal.
    pb.setString_forType_("", "org.nspasteboard.ConcealedType")
    pb.setString_forType_("", "com.nspasteboard.TransientType")
    return True


def _set_pasteboard_string(text: str) -> None:
    """Write *text* to the pasteboard without concealed markers (for restore)."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    ns_str = NSString.stringWithString_(text)
    pb.setString_forType_(ns_str, NSPasteboardTypeString)


def _type_via_clipboard(payload: str) -> bool:
    """Copy to clipboard then simulate Cmd+V."""
    old_clip = _get_pasteboard_string()

    try:
        if not _set_pasteboard_concealed(payload):
            logger.warning("NSPasteboard setString failed")
            return False

        # Small delay to ensure clipboard is ready
        time.sleep(0.05)

        result = subprocess.run(
            [
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            logger.warning("Cmd+V osascript failed: %s",
                           result.stderr.decode(errors="replace"))
            return False
        return True
    except Exception as exc:
        logger.warning("Clipboard injection failed: %s", exc)
        return False
    finally:
        if old_clip is not None:
            def _restore():
                time.sleep(1.0)
                try:
                    _set_pasteboard_string(old_clip)
                except Exception:
                    pass
            threading.Thread(target=_restore, daemon=True).start()


def _type_via_applescript(payload: str) -> bool:
    """Use AppleScript keystroke to type text."""
    try:
        escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning("AppleScript keystroke failed: %s",
                           result.stderr.decode(errors="replace"))
            return False
        return True
    except Exception as exc:
        logger.warning("AppleScript injection failed: %s", exc)
        return False

"""Shared utilities for WKWebView-based panels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Panel close delegate factory
# ---------------------------------------------------------------------------
_close_delegate_cache: dict[str, type] = {}


def make_panel_close_delegate_class(
    class_name: str, *, close_method: str = "close"
) -> type:
    """Create (or return cached) NSObject subclass for panel close delegation.

    Each ObjC class name must be unique across the process, so callers pass a
    distinct *class_name*.  The generated ``windowWillClose_`` calls
    ``getattr(self._panel_ref, close_method)()`` — most panels use ``"close"``
    but some use ``"cancelClicked_"`` or ``"_on_close_button"``.
    """
    key = class_name
    if key in _close_delegate_cache:
        return _close_delegate_cache[key]

    from Foundation import NSObject

    # Build the method dynamically so *close_method* is captured in closure.
    def _window_will_close(self, notification):  # noqa: ARG001
        if self._panel_ref is not None:
            method = getattr(self._panel_ref, close_method)
            if close_method.endswith("_"):
                method(None)
            else:
                method()

    attrs = {
        "_panel_ref": None,
        "windowWillClose_": _window_will_close,
    }
    cls = type(class_name, (NSObject,), attrs)
    _close_delegate_cache[key] = cls
    return cls


def time_range_cutoff(time_range: str) -> Optional[str]:
    """Return ISO timestamp cutoff for a time range value, or None for 'all'."""
    now = datetime.now(timezone.utc)
    if time_range == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range == "7d":
        cutoff = now - timedelta(days=7)
    elif time_range == "30d":
        cutoff = now - timedelta(days=30)
    else:
        return None
    return cutoff.isoformat()


def cleanup_webview_handler(webview, handler_name: str = "action") -> None:
    """Remove a script message handler from a WKWebView, ignoring errors.

    Must be called before releasing the webview to prevent delegate leaks.
    """
    if webview is None:
        return
    try:
        webview.configuration().userContentController().removeScriptMessageHandlerForName_(
            handler_name
        )
    except Exception:
        pass

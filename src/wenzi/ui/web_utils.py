"""Shared utilities for WKWebView-based panels."""

from __future__ import annotations


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

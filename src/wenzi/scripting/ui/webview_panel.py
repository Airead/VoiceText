"""WebViewPanel — NSPanel + WKWebView wrapper with JS<->Python bridge.

Provides a reusable panel for displaying HTML content with bidirectional
communication between JavaScript and Python via a message handler bridge.

Bridge protocol (JS side):
  wz.send(event, data)     — fire-and-forget event to Python
  wz.call(method, data)    — call Python handler, returns Promise
  wz.on(event, callback)   — listen for events from Python

Bridge protocol (Python side):
  panel.send(event, data)  — emit event to JS
  panel.on(event, cb)      — listen for events from JS
  panel.handle(name)(fn)   — register a call handler
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bridge JavaScript injected at document start
# ---------------------------------------------------------------------------

_BRIDGE_JS = r"""
(function() {
    const _handlers = {};
    const _pending = {};
    let _callId = 0;

    const wz = {
        send(event, data) {
            window.webkit.messageHandlers.wz.postMessage(
                {type: 'event', name: event, data: data || null}
            );
        },

        call(method, data, opts) {
            return new Promise(function(resolve, reject) {
                const id = 'c' + (++_callId);
                const timeout = (opts && opts.timeout) || 30000;
                _pending[id] = {resolve: resolve, reject: reject};
                setTimeout(function() {
                    if (_pending[id]) {
                        delete _pending[id];
                        reject(new Error("wz.call timeout: " + method));
                    }
                }, timeout);
                window.webkit.messageHandlers.wz.postMessage(
                    {type: 'call', name: method, data: data || null, callId: id}
                );
            });
        },

        on(event, callback) {
            if (!_handlers[event]) _handlers[event] = [];
            _handlers[event].push(callback);
        },

        _resolve(callId, result) {
            const p = _pending[callId];
            if (p) { delete _pending[callId]; p.resolve(result); }
        },

        _reject(callId, error) {
            const p = _pending[callId];
            if (p) { delete _pending[callId]; p.reject(new Error(error)); }
        },

        _emit(event, data) {
            const cbs = _handlers[event] || [];
            for (const cb of cbs) {
                try { cb(data); } catch(e) { console.error('wz.on handler error:', e); }
            }
        },

        _rejectAll(reason) {
            for (const id of Object.keys(_pending)) {
                const p = _pending[id];
                delete _pending[id];
                p.reject(new Error(reason));
            }
        }
    };

    window.wz = wz;
})();
"""

# ---------------------------------------------------------------------------
# Lazy ObjC classes (avoid PyObjC import at module level)
# ---------------------------------------------------------------------------

_PanelCloseDelegate = None
_MessageHandler = None


def _get_close_delegate_class():
    global _PanelCloseDelegate
    if _PanelCloseDelegate is not None:
        return _PanelCloseDelegate

    from Foundation import NSObject

    class WebViewPanelCloseDelegate(NSObject):
        _panel_ref = None

        def windowWillClose_(self, notification):
            if self._panel_ref is not None:
                self._panel_ref.close()

    _PanelCloseDelegate = WebViewPanelCloseDelegate
    return _PanelCloseDelegate


def _get_message_handler_class():
    global _MessageHandler
    if _MessageHandler is not None:
        return _MessageHandler

    import objc
    from Foundation import NSObject

    import WebKit  # noqa: F401

    WKScriptMessageHandler = objc.protocolNamed("WKScriptMessageHandler")

    class WebViewPanelMessageHandler(NSObject, protocols=[WKScriptMessageHandler]):
        _panel_ref = None

        def userContentController_didReceiveScriptMessage_(
            self, controller, message
        ):
            if self._panel_ref is None:
                return
            raw = message.body()
            # WKWebView bridges JS objects to NSDictionary via PyObjC;
            # convert to a plain Python dict without JSON roundtrip.
            try:
                body = dict(raw) if not isinstance(raw, dict) else raw
            except (TypeError, ValueError):
                logger.warning("Cannot convert webview message: %r", raw)
                return
            self._panel_ref._handle_js_message(body)

    _MessageHandler = WebViewPanelMessageHandler
    return _MessageHandler


# ---------------------------------------------------------------------------
# WebViewPanel
# ---------------------------------------------------------------------------


class WebViewPanel:
    """NSPanel + WKWebView wrapper with bidirectional JS<->Python bridge.

    Args:
        title: Window title.
        html: Initial HTML content to display.
        width: Panel width in points. Default 900.
        height: Panel height in points. Default 700.
        resizable: Whether the panel is resizable. Default True.
        allowed_read_paths: Paths the WKWebView may read from via file:// URLs.
    """

    def __init__(
        self,
        *,
        title: str,
        html: str,
        width: int = 900,
        height: int = 700,
        resizable: bool = True,
        allowed_read_paths: Optional[List[str]] = None,
    ) -> None:
        self._title = title
        self._html = html
        self._width = width
        self._height = height
        self._resizable = resizable
        self._allowed_read_paths = allowed_read_paths or []

        self._panel = None
        self._webview = None
        self._close_delegate = None
        self._message_handler_obj = None
        self._open = False

        # Bridge state
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._call_handlers: Dict[str, Callable] = {}

        # Close callbacks
        self._on_close_callbacks: list = []

        # Temp file for HTML loading with allowed_read_paths
        self._tmp_html_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show the panel, creating it if needed. Safe to call from any thread."""
        if threading.current_thread() is not threading.main_thread():
            from PyObjCTools import AppHelper

            AppHelper.callAfter(self.show)
            return

        from AppKit import NSApp

        NSApp.setActivationPolicy_(0)  # Regular (foreground)

        if self._panel is None:
            self._build_panel()

        self._load_html(self._html)
        self._open = True

        self._panel.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def close(self) -> None:
        """Close panel and restore accessory mode."""
        if not self._open:
            return

        # Fire on_close callbacks
        for cb in self._on_close_callbacks:
            try:
                cb()
            except Exception:
                logger.exception("Error in on_close callback")

        # Reject all pending JS calls (must happen before _open = False)
        self._reject_all_pending("Panel closed")

        self._open = False

        # Clean up temp HTML file
        if self._tmp_html_path is not None:
            try:
                os.unlink(self._tmp_html_path)
            except OSError:
                pass
            self._tmp_html_path = None

        if self._panel is not None:
            from AppKit import NSApp

            self._panel.orderOut_(None)
            NSApp.setActivationPolicy_(1)  # Accessory (statusbar-only)

    def set_html(self, html: str) -> None:
        """Update the HTML content."""
        self._html = html
        if self._webview is not None and self._open:
            self._load_html(html)

    def eval_js(self, js_code: str) -> None:
        """Evaluate JavaScript in the web view."""
        if not self._open or self._webview is None:
            return
        self._webview.evaluateJavaScript_completionHandler_(js_code, None)

    def send(self, event: str, data: Any = None) -> None:
        """Send an event from Python to JavaScript."""
        if not self._open:
            return
        payload = json.dumps(data, ensure_ascii=False)
        js = f"wz._emit({json.dumps(event)}, {payload})"
        self.eval_js(js)

    def on(self, event: str, callback: Callable) -> None:
        """Register a handler for events sent from JavaScript."""
        self._event_handlers[event].append(callback)

    def handle(self, name: str) -> Callable:
        """Decorator to register a call handler for JS wz.call() requests."""
        def decorator(fn: Callable) -> Callable:
            self._call_handlers[name] = fn
            return fn
        return decorator

    def on_close(self, callback: Callable) -> None:
        """Register a callback to be called when the panel is closed."""
        self._on_close_callbacks.append(callback)

    # ------------------------------------------------------------------
    # JS message routing
    # ------------------------------------------------------------------

    def _handle_js_message(self, body: Dict[str, Any]) -> None:
        """Route an incoming message from the JS bridge."""
        msg_type = body.get("type")
        name = body.get("name", "")
        data = body.get("data")

        if msg_type == "event":
            handlers = self._event_handlers.get(name, [])
            for h in handlers:
                try:
                    h(data)
                except Exception:
                    logger.exception("Error in event handler for %r", name)

        elif msg_type == "call":
            call_id = body.get("callId", "")
            if name in self._call_handlers:
                threading.Thread(
                    target=self._run_call_handler,
                    args=(name, data, call_id),
                    daemon=True,
                ).start()
            else:
                self._reject_call(call_id, f"No handler registered for '{name}'")

        else:
            logger.warning("Unknown bridge message type: %r", msg_type)

    def _run_call_handler(self, name: str, data: Any, call_id: str) -> None:
        """Run the call handler (designed for background thread dispatch)."""
        handler = self._call_handlers[name]
        try:
            result = handler(data)
            self._resolve_call(call_id, result)
        except Exception as exc:
            self._reject_call(call_id, str(exc))

    def _resolve_call(self, call_id: str, result: Any) -> None:
        """Send a success response back to JS (dispatched to main thread)."""
        if not self._open:
            return

        def _do():
            payload = json.dumps(
                result if result is not None else None, ensure_ascii=False
            )
            self.eval_js(f"wz._resolve({json.dumps(call_id)}, {payload})")

        try:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(_do)
        except Exception:
            logger.exception("Failed to dispatch resolve to main thread")

    def _reject_call(self, call_id: str, error: str) -> None:
        """Send an error response back to JS (dispatched to main thread)."""
        if not self._open:
            return

        def _do():
            self.eval_js(
                f"wz._reject({json.dumps(call_id)}, {json.dumps(error)})"
            )

        try:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(_do)
        except Exception:
            logger.exception("Failed to dispatch reject to main thread")

    def _reject_all_pending(self, reason: str) -> None:
        """Reject all pending JS calls via the bridge."""
        if self._webview is not None:
            js = f"wz._rejectAll({json.dumps(reason)})"
            self._webview.evaluateJavaScript_completionHandler_(js, None)

    # ------------------------------------------------------------------
    # Panel construction
    # ------------------------------------------------------------------

    def _build_panel(self) -> None:
        """Build NSPanel + WKWebView with bridge injection."""
        from AppKit import (
            NSBackingStoreBuffered,
            NSClosableWindowMask,
            NSMiniaturizableWindowMask,
            NSPanel,
            NSResizableWindowMask,
            NSStatusWindowLevel,
            NSTitledWindowMask,
        )
        from Foundation import NSMakeRect
        from WebKit import (
            WKUserContentController,
            WKUserScript,
            WKUserScriptInjectionTimeAtDocumentStart,
            WKWebView,
            WKWebViewConfiguration,
        )

        style = NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask
        if self._resizable:
            style |= NSResizableWindowMask

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self._width, self._height),
            style,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_(self._title)
        panel.setLevel_(NSStatusWindowLevel)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(False)
        panel.center()

        # Ensure Edit menu for Cmd+C/V/A support in WKWebView
        from wenzi.ui.result_window_web import _ensure_edit_menu

        _ensure_edit_menu()

        # Close delegate
        delegate_cls = _get_close_delegate_class()
        delegate = delegate_cls.alloc().init()
        delegate._panel_ref = self
        panel.setDelegate_(delegate)
        self._close_delegate = delegate

        # WKWebView with bridge script + message handler
        content_controller = WKUserContentController.alloc().init()

        # Inject bridge JS at document start
        bridge_script = WKUserScript.alloc().initWithSource_injectionTime_forMainFrameOnly_(
            _BRIDGE_JS,
            WKUserScriptInjectionTimeAtDocumentStart,
            True,
        )
        content_controller.addUserScript_(bridge_script)

        # Message handler
        handler_cls = _get_message_handler_class()
        handler = handler_cls.alloc().init()
        handler._panel_ref = self
        content_controller.addScriptMessageHandler_name_(handler, "wz")
        self._message_handler_obj = handler

        config = WKWebViewConfiguration.alloc().init()
        config.setUserContentController_(content_controller)

        webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, self._width, self._height),
            config,
        )
        webview.setAutoresizingMask_(0x12)  # Width + Height sizable
        panel.contentView().addSubview_(webview)

        self._panel = panel
        self._webview = webview

    def _load_html(self, html: str) -> None:
        """Load HTML into the webview.

        If allowed_read_paths is set, writes to a temp file and uses
        loadFileURL:allowingReadAccessToURL: so local file:// resources
        are accessible. Otherwise uses loadHTMLString:baseURL:.
        """
        if self._webview is None:
            return

        from Foundation import NSURL

        if self._allowed_read_paths:
            # Write HTML to a temp file so loadFileURL works
            tmp = tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8"
            )
            tmp.write(html)
            tmp.close()

            file_url = NSURL.fileURLWithPath_(tmp.name)
            # Compute common ancestor when multiple paths are provided
            expanded = [os.path.expanduser(p) for p in self._allowed_read_paths]
            access_path = (
                os.path.commonpath(expanded) if len(expanded) > 1 else expanded[0]
            )
            access_url = NSURL.fileURLWithPath_(access_path)
            # Clean up previous temp file before loading new one
            if self._tmp_html_path is not None:
                try:
                    os.unlink(self._tmp_html_path)
                except OSError:
                    pass
            self._tmp_html_path = tmp.name

            self._webview.loadFileURL_allowingReadAccessToURL_(file_url, access_url)
        else:
            self._webview.loadHTMLString_baseURL_(
                html, NSURL.URLWithString_("about:blank")
            )

"""Chooser panel — Alfred/Raycast-style quick launcher.

Uses NSPanel + WKWebView for a search-and-filter UI.
Keyboard-driven: type to filter, ↑↓ to navigate, Enter to execute.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Dict, List, Optional

from voicetext.scripting.sources import ChooserItem, ChooserSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WKScriptMessageHandler (lazy-created to avoid PyObjC import at module level)
# ---------------------------------------------------------------------------
_MessageHandler = None


def _get_message_handler_class():
    global _MessageHandler
    if _MessageHandler is not None:
        return _MessageHandler

    import objc
    from Foundation import NSObject

    import WebKit  # noqa: F401

    WKScriptMessageHandler = objc.protocolNamed("WKScriptMessageHandler")

    class ChooserMessageHandler(NSObject, protocols=[WKScriptMessageHandler]):
        _panel_ref = None

        def userContentController_didReceiveScriptMessage_(
            self, controller, message
        ):
            if self._panel_ref is None:
                return
            raw = message.body()
            try:
                from Foundation import NSJSONSerialization

                json_data, _ = (
                    NSJSONSerialization.dataWithJSONObject_options_error_(
                        raw, 0, None
                    )
                )
                body = json.loads(bytes(json_data))
            except Exception:
                logger.warning("Cannot convert chooser message: %r", raw)
                return
            self._panel_ref._handle_js_message(body)

    _MessageHandler = ChooserMessageHandler
    return _MessageHandler


# ---------------------------------------------------------------------------
# WKNavigationDelegate (lazy-created)
# ---------------------------------------------------------------------------
_NavigationDelegate = None


def _get_navigation_delegate_class():
    global _NavigationDelegate
    if _NavigationDelegate is not None:
        return _NavigationDelegate

    import objc
    from Foundation import NSObject

    import WebKit  # noqa: F401

    WKNavigationDelegate = objc.protocolNamed("WKNavigationDelegate")

    class ChooserNavigationDelegate(NSObject, protocols=[WKNavigationDelegate]):
        _panel_ref = None

        def webView_didFinishNavigation_(self, webview, navigation):
            if self._panel_ref is not None:
                self._panel_ref._on_page_loaded()

    _NavigationDelegate = ChooserNavigationDelegate
    return _NavigationDelegate


# ---------------------------------------------------------------------------
# Borderless key-capable NSPanel subclass (lazy-created)
# ---------------------------------------------------------------------------
_KeyablePanel = None


def _get_keyable_panel_class():
    """Return an NSPanel subclass that can become key window when borderless."""
    global _KeyablePanel
    if _KeyablePanel is not None:
        return _KeyablePanel

    from AppKit import NSPanel

    class ChooserKeyablePanel(NSPanel):
        def canBecomeKeyWindow(self):
            return True

    _KeyablePanel = ChooserKeyablePanel
    return _KeyablePanel


# ---------------------------------------------------------------------------
# Panel delegate for resign-key (lazy-created)
# ---------------------------------------------------------------------------
_PanelDelegate = None


def _get_panel_delegate_class():
    """Return an NSObject subclass that closes the panel on focus loss."""
    global _PanelDelegate
    if _PanelDelegate is not None:
        return _PanelDelegate

    from Foundation import NSObject

    class ChooserPanelDelegate(NSObject):
        _panel_ref = None

        def windowDidResignKey_(self, notification):
            if self._panel_ref is not None:
                self._panel_ref.close()

    _PanelDelegate = ChooserPanelDelegate
    return _PanelDelegate


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class ChooserPanel:
    """Alfred/Raycast-style search launcher panel.

    Manages an NSPanel with WKWebView, dispatches search queries to
    registered ChooserSource instances, and executes item actions.
    """

    _PANEL_WIDTH = 960
    _PANEL_HEIGHT = 400

    def __init__(self) -> None:
        self._panel = None
        self._webview = None
        self._message_handler = None
        self._navigation_delegate = None
        self._panel_delegate = None
        self._page_loaded: bool = False
        self._pending_js: list[str] = []

        self._sources: Dict[str, ChooserSource] = {}
        self._active_source: Optional[str] = None
        self._current_items: List[ChooserItem] = []
        self._items_version: int = 0  # incremented on every setResults push
        self._closing: bool = False

        self._on_close: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Source management
    # ------------------------------------------------------------------

    def register_source(self, source: ChooserSource) -> None:
        """Register a data source."""
        self._sources[source.name] = source
        logger.info("Chooser source registered: %s", source.name)

    def unregister_source(self, name: str) -> None:
        """Remove a data source by name."""
        self._sources.pop(name, None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_visible(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    def show(self, on_close: Optional[Callable] = None) -> None:
        """Show the chooser panel. Must run on main thread."""
        self._on_close = on_close

        if self._panel is not None and self._panel.isVisible():
            # Already visible — just focus
            self._eval_js("focusInput()")
            self._panel.makeKeyAndOrderFront_(None)
            from AppKit import NSApp
            NSApp.activateIgnoringOtherApps_(True)
            return

        self._build_panel()
        self._panel.makeKeyAndOrderFront_(None)

        from AppKit import NSApp
        NSApp.setActivationPolicy_(0)  # Regular (foreground)
        NSApp.activateIgnoringOtherApps_(True)

    def close(self) -> None:
        """Close the chooser panel."""
        if self._closing:
            return
        self._closing = True

        if self._webview is not None:
            self._webview.setNavigationDelegate_(None)
            # Remove the script message handler to break the reference cycle
            try:
                config = self._webview.configuration()
                if config:
                    config.userContentController().removeScriptMessageHandlerForName_(
                        "chooser"
                    )
            except Exception:
                pass
        if self._message_handler is not None:
            self._message_handler._panel_ref = None
        if self._navigation_delegate is not None:
            self._navigation_delegate._panel_ref = None
        if self._panel is not None:
            self._panel.setDelegate_(None)
            self._panel_delegate = None
            self._panel.orderOut_(None)
            self._panel = None
        self._webview = None
        self._message_handler = None
        self._navigation_delegate = None
        self._page_loaded = False
        self._pending_js = []
        self._current_items = []
        self._closing = False

        from AppKit import NSApp
        NSApp.setActivationPolicy_(1)  # Accessory (statusbar-only)

        callback = self._on_close
        self._on_close = None
        if callback is not None:
            callback()

    def toggle(self, on_close: Optional[Callable] = None) -> None:
        """Toggle the chooser panel visibility."""
        if self.is_visible:
            self.close()
        else:
            self.show(on_close=on_close)

    # ------------------------------------------------------------------
    # Search logic
    # ------------------------------------------------------------------

    def _do_search(self, query: str, source_name: Optional[str] = None) -> None:
        """Run a search against the active source and push results to JS."""
        source_name = source_name or self._active_source
        source = self._sources.get(source_name) if source_name else None

        # If no specific source, check for prefix match first
        if source is None:
            for src in self._sources.values():
                if src.prefix and query.startswith(src.prefix):
                    source = src
                    query = query[len(src.prefix):].lstrip()
                    break

        # When searching across all non-prefix sources (no specific source),
        # empty query returns nothing. When a specific source is active
        # (e.g. clipboard via Tab/prefix), let the source decide.
        if source is None:
            if not query.strip():
                self._current_items = []
                self._eval_js("setResults([])")
                return
            all_items = []
            sorted_sources = sorted(
                self._sources.values(),
                key=lambda s: s.priority,
                reverse=True,
            )
            for src in sorted_sources:
                if src.prefix is not None:
                    continue  # Skip prefix-only sources
                if src.search is not None:
                    try:
                        all_items.extend(src.search(query))
                    except Exception:
                        logger.exception("Chooser source %s search error", src.name)
            self._current_items = all_items
        else:
            try:
                self._current_items = source.search(query) if source.search else []
            except Exception:
                logger.exception("Chooser source %s search error", source.name)
                self._current_items = []

        self._push_items_to_js()

    def _push_items_to_js(self) -> None:
        """Serialize current items and send to the web view."""
        self._items_version += 1
        js_items = []
        for item in self._current_items:
            js_item = {
                "title": item.title,
                "subtitle": item.subtitle,
                "icon": item.icon,
                "badge": "",
                "hasReveal": item.reveal_path is not None or item.secondary_action is not None,
            }
            if item.preview is not None:
                js_item["preview"] = item.preview
            js_items.append(js_item)
        self._eval_js(
            f"setResults({json.dumps(js_items, ensure_ascii=False)},"
            f"{self._items_version})"
        )

    # ------------------------------------------------------------------
    # JS message handler
    # ------------------------------------------------------------------

    def _handle_js_message(self, body: dict) -> None:
        """Dispatch messages from JavaScript."""
        msg_type = body.get("type", "")

        if msg_type == "search":
            query = body.get("query", "")
            self._do_search(query)

        elif msg_type == "execute":
            index = body.get("index", 0)
            version = body.get("version", self._items_version)
            self._execute_item(index, version)

        elif msg_type == "reveal":
            index = body.get("index", 0)
            version = body.get("version", self._items_version)
            self._reveal_item(index, version)

        elif msg_type == "close":
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self.close)

        elif msg_type == "switchSource":
            source_name = body.get("source")
            query = body.get("query", "")
            self._active_source = source_name
            self._do_search(query, source_name=source_name)

        elif msg_type == "requestPreview":
            index = body.get("index", -1)
            self._send_preview(index)

    def _execute_item(self, index: int, version: int = 0) -> None:
        """Execute the primary action (Enter): close panel, then act."""
        if version and version != self._items_version:
            logger.debug("Stale execute (v%d != v%d), ignored", version, self._items_version)
            return
        if 0 <= index < len(self._current_items):
            item = self._current_items[index]
            action = item.action
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self.close)
            if action is not None:
                import threading

                def _deferred():
                    import time
                    time.sleep(0.15)  # Let previous app regain focus
                    try:
                        action()
                    except Exception:
                        logger.exception(
                            "Chooser action failed for %r", item.title
                        )

                threading.Thread(target=_deferred, daemon=True).start()

    def _reveal_item(self, index: int, version: int = 0) -> None:
        """Execute the secondary action (Cmd+Enter).

        For apps: reveal in Finder. For other items: call secondary_action.
        """
        if version and version != self._items_version:
            return
        if 0 <= index < len(self._current_items):
            item = self._current_items[index]
            from PyObjCTools import AppHelper

            if item.reveal_path:
                import subprocess
                subprocess.Popen(  # noqa: S603
                    ["open", "-R", item.reveal_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                AppHelper.callAfter(self.close)
            elif item.secondary_action is not None:
                AppHelper.callAfter(self.close)
                try:
                    item.secondary_action()
                except Exception:
                    logger.exception(
                        "Chooser secondary action failed for %r", item.title
                    )

    def _send_preview(self, index: int) -> None:
        """Send preview data for the item at *index* to JS."""
        if 0 <= index < len(self._current_items):
            item = self._current_items[index]
            if item.preview is not None:
                self._eval_js(
                    f"setPreview({json.dumps(item.preview, ensure_ascii=False)})"
                )
                return
        self._eval_js("setPreview(null)")

    # ------------------------------------------------------------------
    # Internal: panel construction
    # ------------------------------------------------------------------

    def _eval_js(self, js_code: str) -> None:
        """Evaluate JavaScript, queuing if page not yet loaded."""
        if self._webview is None:
            return
        if not self._page_loaded:
            self._pending_js.append(js_code)
            return
        self._webview.evaluateJavaScript_completionHandler_(js_code, None)

    def _on_page_loaded(self) -> None:
        """Called when WKWebView finishes loading the HTML."""
        pending = self._pending_js[:]
        self._pending_js.clear()
        self._page_loaded = True
        if pending and self._webview is not None:
            combined = ";".join(pending)
            self._webview.evaluateJavaScript_completionHandler_(combined, None)

        # Push source tabs to JS
        self._push_sources_to_js()

    def _push_sources_to_js(self) -> None:
        """Send the list of registered sources to JS for tab rendering."""
        sorted_sources = sorted(
            self._sources.values(), key=lambda s: s.priority, reverse=True
        )

        src_list = []
        default_name = None
        for src in sorted_sources:
            label = src.name.capitalize()
            if src.prefix:
                label = f"{src.name.capitalize()} ({src.prefix})"
            else:
                # First non-prefix source is the default
                if default_name is None:
                    default_name = src.name
            src_list.append({"name": src.name, "label": label})

        # Fallback: use first source if all have prefixes
        if default_name is None and src_list:
            default_name = src_list[0]["name"]

        if self._active_source is None:
            self._active_source = default_name

        self._eval_js(
            f"setSources({json.dumps(src_list, ensure_ascii=False)},"
            f"{json.dumps(self._active_source)})"
        )

    def _build_panel(self) -> None:
        """Create NSPanel + WKWebView."""
        from AppKit import (
            NSBackingStoreBuffered,
            NSScreen,
            NSStatusWindowLevel,
        )
        from Foundation import NSMakeRect, NSURL
        from WebKit import WKUserContentController, WKWebView, WKWebViewConfiguration

        PanelClass = _get_keyable_panel_class()
        panel = PanelClass.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, self._PANEL_WIDTH, self._PANEL_HEIGHT),
            0,  # Borderless
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSStatusWindowLevel + 1)
        panel.setOpaque_(False)
        panel.setHasShadow_(True)
        panel.setFloatingPanel_(True)
        panel.setHidesOnDeactivate_(True)
        panel.setMovableByWindowBackground_(False)
        panel.setCollectionBehavior_(1 << 4)  # canJoinAllSpaces

        # Transparent background — the HTML provides its own
        from AppKit import NSColor
        panel.setBackgroundColor_(NSColor.clearColor())

        # Close on focus loss
        delegate_cls = _get_panel_delegate_class()
        delegate = delegate_cls.alloc().init()
        delegate._panel_ref = self
        panel.setDelegate_(delegate)
        self._panel_delegate = delegate

        # Round corners
        panel.contentView().setWantsLayer_(True)
        panel.contentView().layer().setCornerRadius_(12.0)
        panel.contentView().layer().setMasksToBounds_(True)

        # Position: center-top of main screen (like Spotlight)
        screen = NSScreen.mainScreen()
        if screen:
            sf = screen.frame()
            x = sf.origin.x + (sf.size.width - self._PANEL_WIDTH) / 2
            y = sf.origin.y + sf.size.height - self._PANEL_HEIGHT - 200
            panel.setFrameOrigin_((x, y))
        else:
            panel.center()

        # WKWebView with message handler
        wk_config = WKWebViewConfiguration.alloc().init()
        content_controller = WKUserContentController.alloc().init()

        handler_cls = _get_message_handler_class()
        handler = handler_cls.alloc().init()
        handler._panel_ref = self
        content_controller.addScriptMessageHandler_name_(handler, "chooser")
        wk_config.setUserContentController_(content_controller)

        webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, self._PANEL_WIDTH, self._PANEL_HEIGHT),
            wk_config,
        )
        webview.setAutoresizingMask_(0x12)  # Width + Height sizable
        webview.setValue_forKey_(False, "drawsBackground")
        panel.contentView().addSubview_(webview)

        # Navigation delegate
        nav_cls = _get_navigation_delegate_class()
        nav_delegate = nav_cls.alloc().init()
        nav_delegate._panel_ref = self
        webview.setNavigationDelegate_(nav_delegate)

        self._panel = panel
        self._webview = webview
        self._message_handler = handler
        self._navigation_delegate = nav_delegate
        self._page_loaded = False
        self._pending_js = []
        self._current_items = []
        self._active_source = None

        # Load HTML
        from voicetext.scripting.ui.chooser_html import CHOOSER_HTML

        webview.loadHTMLString_baseURL_(
            CHOOSER_HTML, NSURL.fileURLWithPath_("/")
        )

"""Tests for WebViewPanel — core panel class with JS bridge communication.

UI/WKWebView parts are not testable in CI — these tests cover the
pure-Python logic: bridge event/call routing, handler registration,
lifecycle state management.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from wenzi.scripting.ui.webview_panel import WebViewPanel


def _make_panel(**kwargs) -> WebViewPanel:
    """Create a WebViewPanel with eval_js mocked (no WKWebView)."""
    panel = WebViewPanel(title="Test", html="<p>hi</p>", **kwargs)
    panel._webview = MagicMock()
    panel._panel = MagicMock()
    panel._open = True
    return panel


# ---------------------------------------------------------------------------
# Construction defaults
# ---------------------------------------------------------------------------


class TestWebViewPanelDefaults:
    def test_default_dimensions(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._width == 900
        assert p._height == 700

    def test_custom_dimensions(self):
        p = WebViewPanel(title="T", html="<b>x</b>", width=400, height=300)
        assert p._width == 400
        assert p._height == 300

    def test_default_resizable(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._resizable is True

    def test_default_allowed_read_paths(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._allowed_read_paths == []

    def test_stores_title_and_html(self):
        p = WebViewPanel(title="My Title", html="<div>content</div>")
        assert p._title == "My Title"
        assert p._html == "<div>content</div>"

    def test_default_titlebar_hidden(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._titlebar_hidden is False

    def test_titlebar_hidden_enabled(self):
        p = WebViewPanel(title="T", html="<b>x</b>", titlebar_hidden=True)
        assert p._titlebar_hidden is True

    def test_titlebar_hidden_registers_close_handler(self):
        p = WebViewPanel(title="T", html="<b>x</b>", titlebar_hidden=True)
        assert "close" in p._event_handlers
        assert len(p._event_handlers["close"]) == 1

    def test_titlebar_visible_no_close_handler(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert "close" not in p._event_handlers

    def test_default_floating(self):
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._floating is True

    def test_floating_disabled(self):
        p = WebViewPanel(title="T", html="<b>x</b>", floating=False)
        assert p._floating is False


# ---------------------------------------------------------------------------
# Bridge: on() / handle() registration
# ---------------------------------------------------------------------------


class TestWebViewPanelBridge:
    def test_on_registers_event_handler(self):
        panel = _make_panel()
        cb = MagicMock()
        panel.on("my_event", cb)
        assert "my_event" in panel._event_handlers
        assert cb in panel._event_handlers["my_event"]

    def test_on_multiple_handlers_same_event(self):
        panel = _make_panel()
        cb1 = MagicMock()
        cb2 = MagicMock()
        panel.on("evt", cb1)
        panel.on("evt", cb2)
        assert len(panel._event_handlers["evt"]) == 2

    def test_handle_decorator_registers(self):
        panel = _make_panel()

        @panel.handle("do_stuff")
        def handler(data):
            return "ok"

        assert "do_stuff" in panel._call_handlers
        assert panel._call_handlers["do_stuff"] is handler

    def test_handle_js_message_routes_event(self):
        panel = _make_panel()
        cb = MagicMock()
        panel.on("ping", cb)

        panel._handle_js_message({"type": "event", "name": "ping", "data": {"x": 1}})
        cb.assert_called_once_with({"x": 1})

    def test_handle_js_message_routes_event_multiple_handlers(self):
        panel = _make_panel()
        cb1 = MagicMock()
        cb2 = MagicMock()
        panel.on("ping", cb1)
        panel.on("ping", cb2)

        panel._handle_js_message({"type": "event", "name": "ping", "data": 42})
        cb1.assert_called_once_with(42)
        cb2.assert_called_once_with(42)

    def test_handle_js_message_event_no_handler_no_error(self):
        """Events with no registered handler should be silently ignored."""
        panel = _make_panel()
        # Should not raise
        panel._handle_js_message({"type": "event", "name": "unknown", "data": None})

    @patch("wenzi.scripting.ui.webview_panel.threading.Thread")
    def test_handle_js_message_routes_call(self, mock_thread_cls):
        """Call messages should dispatch to _run_call_handler on a background thread."""
        panel = _make_panel()
        handler = MagicMock(return_value="result")
        panel._call_handlers["greet"] = handler

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        panel._handle_js_message(
            {"type": "call", "name": "greet", "data": "hello", "callId": "c1"}
        )
        mock_thread_cls.assert_called_once()
        call_kwargs = mock_thread_cls.call_args
        assert call_kwargs[1]["target"] == panel._run_call_handler
        assert call_kwargs[1]["args"] == ("greet", "hello", "c1")
        assert call_kwargs[1]["daemon"] is True
        mock_thread.start.assert_called_once()

    def test_handle_js_message_call_no_handler_rejects(self):
        """Call with no registered handler should resolve with error."""
        panel = _make_panel()

        with patch.object(panel, "_reject_call") as mock_reject:
            panel._handle_js_message(
                {"type": "call", "name": "missing", "data": None, "callId": "c2"}
            )
            mock_reject.assert_called_once()
            args = mock_reject.call_args
            assert args[0][0] == "c2"
            assert "missing" in args[0][1]

    def test_send_calls_eval_js(self):
        panel = _make_panel()
        panel.send("myEvent", {"key": "val"})

        panel._webview.evaluateJavaScript_completionHandler_.assert_called_once()
        js_code = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "myEvent" in js_code
        assert "val" in js_code

    def test_send_ignored_when_closed(self):
        panel = _make_panel()
        panel._open = False
        panel.send("myEvent", {"key": "val"})
        panel._webview.evaluateJavaScript_completionHandler_.assert_not_called()

    def test_eval_js_ignored_when_closed(self):
        panel = _make_panel()
        panel._open = False
        panel.eval_js("alert(1)")
        panel._webview.evaluateJavaScript_completionHandler_.assert_not_called()

    def test_set_html_updates_stored_html(self):
        panel = _make_panel()
        panel.set_html("<p>new</p>")
        assert panel._html == "<p>new</p>"

    def test_run_call_handler_success(self):
        """_run_call_handler should call handler and resolve on success."""
        panel = _make_panel()
        handler = MagicMock(return_value={"status": "ok"})
        panel._call_handlers["action"] = handler

        with patch.object(panel, "_resolve_call") as mock_resolve:
            panel._run_call_handler("action", {"input": 1}, "c5")
            handler.assert_called_once_with({"input": 1})
            mock_resolve.assert_called_once_with("c5", {"status": "ok"})

    def test_run_call_handler_error(self):
        """_run_call_handler should reject on handler exception."""
        panel = _make_panel()
        handler = MagicMock(side_effect=ValueError("boom"))
        panel._call_handlers["bad"] = handler

        with patch.object(panel, "_reject_call") as mock_reject:
            panel._run_call_handler("bad", None, "c6")
            mock_reject.assert_called_once()
            assert "c6" == mock_reject.call_args[0][0]
            assert "boom" in mock_reject.call_args[0][1]

    def test_resolve_call_dispatches_via_apphelper(self):
        panel = _make_panel()
        mock_apphelper = MagicMock()
        mock_apphelper.callAfter.side_effect = lambda fn: fn()

        mock_pyobjctools = MagicMock()
        mock_pyobjctools.AppHelper = mock_apphelper

        with patch.dict("sys.modules", {
            "PyObjCTools": mock_pyobjctools,
            "PyObjCTools.AppHelper": mock_apphelper,
        }):
            panel._resolve_call("c10", {"msg": "done"})

        panel._webview.evaluateJavaScript_completionHandler_.assert_called_once()
        js_code = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "c10" in js_code
        assert "_resolve" in js_code

    def test_reject_call_dispatches_via_apphelper(self):
        panel = _make_panel()
        mock_apphelper = MagicMock()
        mock_apphelper.callAfter.side_effect = lambda fn: fn()

        mock_pyobjctools = MagicMock()
        mock_pyobjctools.AppHelper = mock_apphelper

        with patch.dict("sys.modules", {
            "PyObjCTools": mock_pyobjctools,
            "PyObjCTools.AppHelper": mock_apphelper,
        }):
            panel._reject_call("c11", "something failed")

        panel._webview.evaluateJavaScript_completionHandler_.assert_called_once()
        js_code = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "c11" in js_code
        assert "_reject" in js_code


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestWebViewPanelLifecycle:
    def test_close_silences_subsequent_sends(self):
        panel = _make_panel()
        with patch.dict("sys.modules", {"AppKit": MagicMock()}):
            panel.close()
        assert panel._open is False
        # Reset mock to clear the _rejectAll call made during close()
        panel._webview.evaluateJavaScript_completionHandler_.reset_mock()
        panel.send("evt", {})
        panel._webview.evaluateJavaScript_completionHandler_.assert_not_called()

    def test_double_close_is_noop(self):
        panel = _make_panel()
        with patch.dict("sys.modules", {"AppKit": MagicMock()}):
            panel.close()
            # Second close should not raise (already not open)
            panel.close()
        assert panel._open is False

    def test_initial_state_is_not_open(self):
        """Before show() is called, the panel should not be open."""
        p = WebViewPanel(title="T", html="<b>x</b>")
        assert p._open is False

    def test_close_calls_reject_all_pending(self):
        """Closing should invoke _reject_all_pending before setting _open=False."""
        panel = _make_panel()
        open_during_reject = []

        original = panel._reject_all_pending

        def spy(reason):
            open_during_reject.append(panel._open)
            original(reason)

        panel._reject_all_pending = spy

        with patch.dict("sys.modules", {"AppKit": MagicMock()}):
            panel.close()

        # _reject_all_pending was called while _open was still True
        assert open_during_reject == [True]

    def test_close_cleans_up_tmp_html(self, tmp_path):
        """Closing should delete the temp HTML file."""
        panel = _make_panel()
        tmp_file = tmp_path / "test.html"
        tmp_file.write_text("<p>hi</p>")
        panel._tmp_html_path = str(tmp_file)

        with patch.dict("sys.modules", {"AppKit": MagicMock()}):
            panel.close()

        assert not tmp_file.exists()
        assert panel._tmp_html_path is None

    def test_on_close_callback_called(self):
        panel = WebViewPanel(title="T", html="<p>hi</p>")
        called = []
        panel.on_close(lambda: called.append(True))
        panel._panel = None  # no real NSPanel
        panel._open = True
        panel.close()
        assert called == [True]

    def test_on_close_not_called_on_double_close(self):
        panel = WebViewPanel(title="T", html="<p>hi</p>")
        called = []
        panel.on_close(lambda: called.append(1))
        panel._panel = None
        panel._open = True
        panel.close()
        panel.close()
        assert called == [1]  # only called once

    @patch("wenzi.scripting.ui.webview_panel.threading.Thread")
    def test_call_dispatches_to_background_thread(self, mock_thread_cls):
        panel = WebViewPanel(title="T", html="<p>hi</p>")
        panel._open = True

        @panel.handle("compute")
        def compute(data):
            return 42

        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        panel._handle_js_message({
            "type": "call",
            "name": "compute",
            "data": {"n": 1},
            "callId": "req-1",
        })
        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()

    def test_resolve_call_skipped_when_closed(self):
        """_resolve_call should be a no-op when panel is closed."""
        panel = _make_panel()
        panel._open = False
        panel._resolve_call("c20", "result")
        panel._webview.evaluateJavaScript_completionHandler_.assert_not_called()

    def test_reject_call_skipped_when_closed(self):
        """_reject_call should be a no-op when panel is closed."""
        panel = _make_panel()
        panel._open = False
        panel._reject_call("c21", "error")
        panel._webview.evaluateJavaScript_completionHandler_.assert_not_called()

    def test_no_pending_calls_attribute(self):
        """_pending_calls was dead code and should no longer exist."""
        panel = WebViewPanel(title="T", html="<b>x</b>")
        assert not hasattr(panel, "_pending_calls")

    def test_tmp_html_path_default_none(self):
        """Temp HTML path should start as None."""
        panel = WebViewPanel(title="T", html="<b>x</b>")
        assert panel._tmp_html_path is None

    def test_reject_all_pending_fires_js_when_webview_exists(self):
        """_reject_all_pending should call evaluateJavaScript when webview exists."""
        panel = _make_panel()
        panel._reject_all_pending("closing")
        panel._webview.evaluateJavaScript_completionHandler_.assert_called_once()
        js = panel._webview.evaluateJavaScript_completionHandler_.call_args[0][0]
        assert "_rejectAll" in js
        assert "closing" in js

    def test_reject_all_pending_noop_without_webview(self):
        """_reject_all_pending should be a no-op when webview is None."""
        panel = WebViewPanel(title="T", html="<b>x</b>")
        panel._open = True
        # Should not raise
        panel._reject_all_pending("closing")


# ---------------------------------------------------------------------------
# Bridge JS
# ---------------------------------------------------------------------------


class TestBridgeJS:
    def test_bridge_js_contains_timeout(self):
        """wz.call() should include a setTimeout for timeout handling."""
        from wenzi.scripting.ui.webview_panel import _BRIDGE_JS

        assert "setTimeout" in _BRIDGE_JS
        assert "wz.call timeout" in _BRIDGE_JS
        assert "30000" in _BRIDGE_JS

    def test_bridge_js_call_accepts_opts(self):
        """wz.call() should accept opts parameter with timeout."""
        from wenzi.scripting.ui.webview_panel import _BRIDGE_JS

        assert "call(method, data, opts)" in _BRIDGE_JS
        assert "opts.timeout" in _BRIDGE_JS


# ---------------------------------------------------------------------------
# allowed_read_paths commonpath
# ---------------------------------------------------------------------------


class TestAllowedReadPaths:
    def test_commonpath_with_multiple_paths(self):
        """Multiple allowed_read_paths should use os.path.commonpath."""
        panel = WebViewPanel(
            title="T",
            html="<b>x</b>",
            allowed_read_paths=["/a/b/c", "/a/b/d"],
        )
        expanded = [os.path.expanduser(p) for p in panel._allowed_read_paths]
        result = os.path.commonpath(expanded)
        assert result == "/a/b"

    def test_single_path_used_directly(self):
        """Single allowed_read_path should be used as-is."""
        panel = WebViewPanel(
            title="T",
            html="<b>x</b>",
            allowed_read_paths=["/my/path"],
        )
        expanded = [os.path.expanduser(p) for p in panel._allowed_read_paths]
        assert len(expanded) == 1
        assert expanded[0] == "/my/path"

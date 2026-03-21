"""Tests for the wz.ui API."""


class TestUIAPI:
    def test_webview_panel_returns_panel(self):
        from wenzi.scripting.api.ui import UIAPI

        api = UIAPI()
        panel = api.webview_panel(title="Test", html="<p>hi</p>")

        from wenzi.scripting.ui.webview_panel import WebViewPanel

        assert isinstance(panel, WebViewPanel)
        assert panel._title == "Test"

    def test_webview_panel_with_all_params(self):
        from wenzi.scripting.api.ui import UIAPI

        api = UIAPI()
        panel = api.webview_panel(
            title="Full",
            html="<h1>Hello</h1>",
            width=1024,
            height=768,
            resizable=False,
            allowed_read_paths=["/tmp"],
        )
        assert panel._width == 1024
        assert panel._height == 768
        assert panel._resizable is False
        assert panel._allowed_read_paths == ["/tmp"]

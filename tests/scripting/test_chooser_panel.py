"""Tests for ChooserPanel search logic and source management.

UI/WKWebView parts are not testable in CI — these tests cover the
pure-Python logic: source registration, search dispatch, item execution.
"""

import json
from unittest.mock import MagicMock, patch

from voicetext.scripting.sources import ChooserItem, ChooserSource
from voicetext.scripting.ui.chooser_panel import ChooserPanel


def _make_panel():
    """Create a ChooserPanel with _eval_js mocked (no WKWebView)."""
    panel = ChooserPanel()
    panel._eval_js = MagicMock()
    panel._page_loaded = True
    return panel


def _make_source(name, prefix=None, items=None, priority=0):
    """Create a ChooserSource with a simple substring search."""
    items = items or []

    def _search(query):
        return [i for i in items if query.lower() in i.title.lower()]

    return ChooserSource(name=name, prefix=prefix, search=_search, priority=priority)


class TestSourceRegistration:
    def test_register_source(self):
        panel = _make_panel()
        src = _make_source("apps")
        panel.register_source(src)
        assert "apps" in panel._sources

    def test_unregister_source(self):
        panel = _make_panel()
        panel.register_source(_make_source("apps"))
        panel.unregister_source("apps")
        assert "apps" not in panel._sources

    def test_unregister_nonexistent(self):
        panel = _make_panel()
        panel.unregister_source("nope")  # Should not raise


class TestSearchLogic:
    def test_empty_query_returns_no_results(self):
        panel = _make_panel()
        panel.register_source(
            _make_source("apps", items=[ChooserItem(title="Safari")])
        )
        panel._do_search("")
        assert panel._current_items == []

    def test_whitespace_query_returns_no_results(self):
        panel = _make_panel()
        panel.register_source(
            _make_source("apps", items=[ChooserItem(title="Safari")])
        )
        panel._do_search("   ")
        assert panel._current_items == []

    def test_search_non_prefix_sources(self):
        panel = _make_panel()
        panel.register_source(
            _make_source(
                "apps",
                items=[
                    ChooserItem(title="Safari"),
                    ChooserItem(title="Slack"),
                    ChooserItem(title="WeChat"),
                ],
            )
        )
        panel._do_search("sa")
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "Safari"

    def test_search_skips_prefix_sources(self):
        panel = _make_panel()
        panel.register_source(
            _make_source(
                "apps",
                items=[ChooserItem(title="Safari")],
            )
        )
        panel.register_source(
            _make_source(
                "clipboard",
                prefix=">cb",
                items=[ChooserItem(title="Safari URL copied")],
            )
        )
        panel._do_search("Safari")
        # Should only get the apps result, not clipboard
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "Safari"

    def test_search_with_prefix_activates_source(self):
        panel = _make_panel()
        panel.register_source(
            _make_source(
                "clipboard",
                prefix=">cb",
                items=[
                    ChooserItem(title="hello world"),
                    ChooserItem(title="https://github.com"),
                ],
            )
        )
        panel._do_search(">cb hello")
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "hello world"

    def test_search_merges_multiple_non_prefix_sources(self):
        panel = _make_panel()
        panel.register_source(
            _make_source(
                "apps",
                items=[ChooserItem(title="Safari")],
                priority=10,
            )
        )
        panel.register_source(
            _make_source(
                "bookmarks",
                items=[ChooserItem(title="Safari Tips")],
                priority=5,
            )
        )
        panel._do_search("Safari")
        assert len(panel._current_items) == 2
        # Higher priority source first
        assert panel._current_items[0].title == "Safari"
        assert panel._current_items[1].title == "Safari Tips"

    def test_search_with_explicit_source_name(self):
        panel = _make_panel()
        panel.register_source(
            _make_source(
                "apps",
                items=[ChooserItem(title="Safari")],
            )
        )
        panel.register_source(
            _make_source(
                "bookmarks",
                items=[ChooserItem(title="Safari Tips")],
            )
        )
        panel._active_source = "bookmarks"
        panel._do_search("Safari", source_name="bookmarks")
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "Safari Tips"

    def test_search_error_handling(self):
        """Source raising an exception should not crash the panel."""
        panel = _make_panel()

        def bad_search(query):
            raise RuntimeError("boom")

        panel.register_source(
            ChooserSource(name="broken", search=bad_search)
        )
        panel._do_search("test")
        assert panel._current_items == []


class TestItemExecution:
    def test_execute_item(self):
        import time

        called = []
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(title="Safari", action=lambda: called.append("safari")),
            ChooserItem(title="Chrome", action=lambda: called.append("chrome")),
        ]
        # Mock close to avoid NSApp calls
        panel.close = MagicMock()
        with patch("PyObjCTools.AppHelper.callAfter", side_effect=lambda fn: fn()):
            panel._execute_item(0)
        # Action runs in a deferred thread with 0.15s delay
        time.sleep(0.3)
        assert called == ["safari"]
        panel.close.assert_called_once()

    def test_execute_item_no_action(self):
        """Item with no action should not crash."""
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="No Action")]
        panel.close = MagicMock()
        with patch("PyObjCTools.AppHelper.callAfter", side_effect=lambda fn: fn()):
            panel._execute_item(0)  # Should not raise

    def test_execute_item_out_of_range(self):
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="Only")]
        with patch("PyObjCTools.AppHelper.callAfter"):
            panel._execute_item(5)  # Should not raise

    def test_reveal_item(self):
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(
                title="Safari",
                reveal_path="/Applications/Safari.app",
            ),
        ]
        panel.close = MagicMock()
        with patch("subprocess.Popen") as mock_popen, \
             patch("PyObjCTools.AppHelper.callAfter", side_effect=lambda fn: fn()):
            panel._reveal_item(0)
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args == ["open", "-R", "/Applications/Safari.app"]

    def test_reveal_item_no_path(self):
        """Item without reveal_path should be a no-op."""
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="No Path")]

        with patch("subprocess.Popen") as mock_popen:
            panel._reveal_item(0)
            mock_popen.assert_not_called()

    def test_secondary_action(self):
        """Cmd+Enter should call secondary_action when no reveal_path."""
        called = []
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(
                title="Clipboard entry",
                secondary_action=lambda: called.append("copied"),
            ),
        ]
        panel.close = MagicMock()
        with patch("PyObjCTools.AppHelper.callAfter", side_effect=lambda fn: fn()):
            panel._reveal_item(0)
        assert called == ["copied"]

    def test_stale_version_rejected(self):
        """Execute with an old version should be ignored."""
        called = []
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(title="Old", action=lambda: called.append("old")),
        ]
        panel._items_version = 5
        panel.close = MagicMock()
        with patch("PyObjCTools.AppHelper.callAfter"):
            panel._execute_item(0, version=3)  # stale
        assert called == []
        panel.close.assert_not_called()


class TestJSMessageHandling:
    def test_search_message(self):
        panel = _make_panel()
        panel.register_source(
            _make_source("apps", items=[ChooserItem(title="Safari")])
        )
        panel._handle_js_message({"type": "search", "query": "saf"})
        assert len(panel._current_items) == 1

    def test_close_message(self):
        panel = _make_panel()
        with patch("PyObjCTools.AppHelper.callAfter") as mock_call_after:
            panel._handle_js_message({"type": "close"})
            mock_call_after.assert_called_once()

    def test_execute_message(self):
        import time

        called = []
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(title="Test", action=lambda: called.append(True))
        ]
        panel.close = MagicMock()
        with patch("PyObjCTools.AppHelper.callAfter", side_effect=lambda fn: fn()):
            panel._handle_js_message({"type": "execute", "index": 0})
        time.sleep(0.3)
        assert called == [True]

    def test_switch_source_message(self):
        panel = _make_panel()
        panel.register_source(_make_source("apps"))
        panel.register_source(_make_source("bookmarks"))
        panel._handle_js_message(
            {"type": "switchSource", "source": "bookmarks", "query": ""}
        )
        assert panel._active_source == "bookmarks"

    def test_request_preview_message(self):
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(
                title="Hello",
                preview={"type": "text", "content": "full text"},
            )
        ]
        panel._handle_js_message({"type": "requestPreview", "index": 0})
        call_args = panel._eval_js.call_args[0][0]
        assert "setPreview" in call_args
        assert "full text" in call_args

    def test_request_preview_no_preview(self):
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="No Preview")]
        panel._handle_js_message({"type": "requestPreview", "index": 0})
        call_args = panel._eval_js.call_args[0][0]
        assert "setPreview(null)" in call_args

    def test_request_preview_out_of_range(self):
        panel = _make_panel()
        panel._current_items = []
        panel._handle_js_message({"type": "requestPreview", "index": 5})
        call_args = panel._eval_js.call_args[0][0]
        assert "setPreview(null)" in call_args


class TestPushItemsToJS:
    def test_serializes_items(self):
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(title="Safari", subtitle="Web browser",
                        reveal_path="/Applications/Safari.app"),
            ChooserItem(title="Clipboard entry"),
        ]
        panel._push_items_to_js()
        call_args = panel._eval_js.call_args[0][0]
        assert '"Safari"' in call_args
        assert '"Web browser"' in call_args
        assert '"hasReveal": true' in call_args

    def test_serializes_preview(self):
        panel = _make_panel()
        panel._current_items = [
            ChooserItem(
                title="Test",
                preview={"type": "text", "content": "hello world"},
            ),
        ]
        panel._push_items_to_js()
        call_args = panel._eval_js.call_args[0][0]
        # Format: setResults([...],version) — extract the JSON array
        inner = call_args[len("setResults("):-1]
        json_part = inner.rsplit(",", 1)[0]
        parsed = json.loads(json_part)
        assert parsed[0]["preview"]["type"] == "text"
        assert parsed[0]["preview"]["content"] == "hello world"

    def test_no_preview_key_when_none(self):
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="Test")]
        panel._push_items_to_js()
        call_args = panel._eval_js.call_args[0][0]
        inner = call_args[len("setResults("):-1]
        json_part = inner.rsplit(",", 1)[0]
        parsed = json.loads(json_part)
        assert "preview" not in parsed[0]

    def test_version_increments(self):
        panel = _make_panel()
        panel._current_items = [ChooserItem(title="A")]
        panel._push_items_to_js()
        v1 = panel._items_version
        panel._current_items = [ChooserItem(title="B")]
        panel._push_items_to_js()
        v2 = panel._items_version
        assert v2 == v1 + 1

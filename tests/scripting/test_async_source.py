"""Tests for async source search support."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

from wenzi.scripting.sources import ChooserItem, ChooserSource
from wenzi.scripting.api.chooser import ChooserAPI


def _wait_for(predicate, timeout=5.0, interval=0.05):
    """Poll until predicate returns True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# ChooserSource dataclass — new fields
# ---------------------------------------------------------------------------

class TestChooserSourceAsyncFields:
    def test_defaults(self):
        src = ChooserSource(name="test")
        assert src.is_async is False
        assert src.search_timeout == 5.0

    def test_custom_values(self):
        src = ChooserSource(name="test", is_async=True, search_timeout=3.0)
        assert src.is_async is True
        assert src.search_timeout == 3.0


# ---------------------------------------------------------------------------
# Source decorator — async detection
# ---------------------------------------------------------------------------

class TestSourceDecoratorAsyncDetection:
    def test_sync_source_not_async(self):
        api = ChooserAPI()

        @api.source("sync-test", prefix="st")
        def search_sync(query):
            return [{"title": f"sync-{query}"}]

        src = api.panel._sources["sync-test"]
        assert src.is_async is False

    def test_async_source_detected(self):
        api = ChooserAPI()

        @api.source("async-test", prefix="at", search_timeout=2.0)
        async def search_async(query):
            return [{"title": f"async-{query}"}]

        src = api.panel._sources["async-test"]
        assert src.is_async is True
        assert src.search_timeout == 2.0
        assert asyncio.iscoroutinefunction(src.search)

    def test_async_source_default_timeout(self):
        api = ChooserAPI()

        @api.source("async-default")
        async def search_async(query):
            return []

        src = api.panel._sources["async-default"]
        assert src.search_timeout == 5.0


# ---------------------------------------------------------------------------
# ChooserPanel — _do_search sync/async split
# ---------------------------------------------------------------------------

class TestDoSearchSyncAsyncSplit:
    """Test that _do_search partitions sources correctly."""

    def _make_panel(self):
        api = ChooserAPI()
        panel = api.panel
        panel._eval_js = MagicMock()
        return panel

    def test_sync_source_works_unchanged(self):
        panel = self._make_panel()
        panel.register_source(ChooserSource(
            name="apps",
            search=lambda q: [ChooserItem(title=f"App-{q}")],
        ))
        panel._do_search("hello")
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "App-hello"

    def test_generation_counter_increments(self):
        panel = self._make_panel()
        panel.register_source(ChooserSource(
            name="apps",
            search=lambda q: [ChooserItem(title="a")],
        ))
        panel._do_search("a")
        gen1 = panel._search_generation
        panel._do_search("b")
        gen2 = panel._search_generation
        assert gen2 == gen1 + 1

    def test_async_source_triggers_launch(self):
        panel = self._make_panel()

        async def async_search(query):
            return [ChooserItem(title=f"async-{query}")]

        panel.register_source(ChooserSource(
            name="async-src",
            search=async_search,
            is_async=True,
        ))

        with patch.object(panel, "_launch_async_search") as mock_launch:
            panel._do_search("test")
            mock_launch.assert_called_once()
            args = mock_launch.call_args
            assert args[0][0].name == "async-src"
            assert args[0][1] == "test"

    def test_sync_results_immediate_async_deferred(self):
        """Sync sources produce immediate items; async sources are deferred."""
        panel = self._make_panel()
        panel.register_source(ChooserSource(
            name="sync-src",
            search=lambda q: [ChooserItem(title="sync")],
        ))

        async def async_search(query):
            return [ChooserItem(title="async")]

        panel.register_source(ChooserSource(
            name="async-src",
            search=async_search,
            is_async=True,
        ))

        with patch.object(panel, "_launch_async_search"):
            panel._do_search("test")

        # Sync items are immediately available
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "sync"

    def test_loading_indicator_set_for_async(self):
        panel = self._make_panel()

        async def async_search(query):
            return []

        panel.register_source(ChooserSource(
            name="async-src",
            search=async_search,
            is_async=True,
        ))

        with patch.object(panel, "_launch_async_search"):
            panel._do_search("test")

        js_calls = [str(c) for c in panel._eval_js.call_args_list]
        assert any("setLoading(true)" in c for c in js_calls)

    def test_no_loading_for_sync_only(self):
        panel = self._make_panel()
        panel.register_source(ChooserSource(
            name="sync-src",
            search=lambda q: [ChooserItem(title="sync")],
        ))
        panel._do_search("test")

        # Loading was never shown — _set_loading(False) is a no-op
        assert panel._loading_visible is False
        js_calls = [str(c) for c in panel._eval_js.call_args_list]
        assert not any("setLoading(true)" in c for c in js_calls)

    def test_empty_query_clears_loading(self):
        panel = self._make_panel()
        panel._pending_async_count = 2  # simulate in-flight
        panel._loading_visible = True  # simulate loading was shown
        panel._do_search("")

        assert panel._pending_async_count == 0
        assert panel._loading_visible is False
        js_calls = [str(c) for c in panel._eval_js.call_args_list]
        assert any("setLoading(false)" in c for c in js_calls)

    def test_prefix_async_source(self):
        """Prefix-activated async source should launch async search."""
        panel = self._make_panel()

        async def async_search(query):
            return [ChooserItem(title=f"prefix-{query}")]

        panel.register_source(ChooserSource(
            name="api-src",
            prefix="api",
            search=async_search,
            is_async=True,
        ))

        with patch.object(panel, "_launch_async_search") as mock_launch:
            panel._do_search("api hello")
            mock_launch.assert_called_once()
            # Verify prefix was stripped
            assert mock_launch.call_args[0][1] == "hello"

        # No sync items
        assert len(panel._current_items) == 0

    def test_prefix_sync_source_unchanged(self):
        panel = self._make_panel()
        panel.register_source(ChooserSource(
            name="cb",
            prefix="cb",
            search=lambda q: [ChooserItem(title=f"clip-{q}")],
        ))
        panel._do_search("cb test")
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "clip-test"


# ---------------------------------------------------------------------------
# _merge_async_results
# ---------------------------------------------------------------------------

class TestMergeAsyncResults:
    def _make_panel(self):
        api = ChooserAPI()
        panel = api.panel
        panel._eval_js = MagicMock()
        return panel

    def test_merge_appends_items(self):
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1
        panel._current_items = [ChooserItem(title="sync")]

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(
            src,
            [ChooserItem(title="async")],
            generation=1,
        )
        assert len(panel._current_items) == 2
        assert panel._current_items[1].title == "async"

    def test_stale_generation_discarded(self):
        panel = self._make_panel()
        panel._search_generation = 5
        panel._pending_async_count = 1
        panel._current_items = [ChooserItem(title="sync")]

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(
            src,
            [ChooserItem(title="stale")],
            generation=3,  # old generation
        )
        # Items NOT merged
        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "sync"

    def test_loading_cleared_when_last_async_completes(self):
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1
        panel._loading_visible = True  # loading was turned on

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(src, [], generation=1)

        assert panel._pending_async_count == 0
        assert panel._loading_visible is False
        js_calls = [str(c) for c in panel._eval_js.call_args_list]
        assert any("setLoading(false)" in c for c in js_calls)

    def test_loading_not_cleared_while_others_pending(self):
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 2

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(
            src,
            [ChooserItem(title="first")],
            generation=1,
        )

        assert panel._pending_async_count == 1
        js_calls = [str(c) for c in panel._eval_js.call_args_list]
        assert not any("setLoading(false)" in c for c in js_calls)

    def test_respects_max_total_results(self):
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1
        # Fill up to near the limit
        panel._current_items = [
            ChooserItem(title=f"item-{i}")
            for i in range(panel._MAX_TOTAL_RESULTS - 1)
        ]

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(
            src,
            [ChooserItem(title="a1"), ChooserItem(title="a2")],
            generation=1,
        )
        # Only 1 slot remaining, so only 1 async item added
        assert len(panel._current_items) == panel._MAX_TOTAL_RESULTS
        assert panel._current_items[-1].title == "a1"

    def test_preserve_selection_on_merge(self):
        """Merged results should use preserve_selection=True."""
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1
        panel._current_items = [ChooserItem(title="sync")]

        src = ChooserSource(name="async-src", is_async=True)
        panel._merge_async_results(
            src,
            [ChooserItem(title="async")],
            generation=1,
        )

        # Check that _push_items_to_js was called with preserve_selection
        # by inspecting the JS output for the -2 sentinel
        js_calls = " ".join(str(c) for c in panel._eval_js.call_args_list)
        assert ",-2" in js_calls


# ---------------------------------------------------------------------------
# Integration: _launch_async_search with real event loop
# ---------------------------------------------------------------------------

class TestLaunchAsyncSearchIntegration:
    """Integration tests using the real asyncio event loop."""

    def _make_panel(self):
        api = ChooserAPI()
        panel = api.panel
        panel._eval_js = MagicMock()
        return panel

    @patch("wenzi.scripting.ui.chooser_panel.AppHelper", create=True)
    def test_async_source_results_merged(self, _mock_apphelper):
        """Async source results are delivered via _merge_async_results."""
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1

        merge_calls = []
        original_merge = panel._merge_async_results

        def capture_merge(*args, **kwargs):
            merge_calls.append(args)
            original_merge(*args, **kwargs)

        panel._merge_async_results = capture_merge

        async def fast_search(query):
            await asyncio.sleep(0.05)
            return [ChooserItem(title=f"fast-{query}")]

        src = ChooserSource(
            name="fast",
            search=fast_search,
            is_async=True,
            search_timeout=2.0,
        )

        # Mock AppHelper.callAfter to call the function directly
        def call_directly(fn, *args, **kwargs):
            fn(*args, **kwargs)

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=call_directly,
        ):
            panel._launch_async_search(src, "hello", generation=1)
            assert _wait_for(lambda: len(merge_calls) > 0, timeout=5.0)

        assert len(panel._current_items) == 1
        assert panel._current_items[0].title == "fast-hello"

    @patch("wenzi.scripting.ui.chooser_panel.AppHelper", create=True)
    def test_async_source_timeout(self, _mock_apphelper):
        """Async source that exceeds timeout returns empty results."""
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1

        merge_calls = []
        original_merge = panel._merge_async_results

        def capture_merge(*args, **kwargs):
            merge_calls.append(args)
            original_merge(*args, **kwargs)

        panel._merge_async_results = capture_merge

        async def slow_search(query):
            await asyncio.sleep(10.0)  # Much longer than timeout
            return [ChooserItem(title="should-not-appear")]

        src = ChooserSource(
            name="slow",
            search=slow_search,
            is_async=True,
            search_timeout=0.1,  # Very short timeout
        )

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=lambda fn, *a, **kw: fn(*a, **kw),
        ):
            panel._launch_async_search(src, "hello", generation=1)
            assert _wait_for(lambda: len(merge_calls) > 0, timeout=5.0)

        # Timed out — no items merged
        assert len(panel._current_items) == 0

    @patch("wenzi.scripting.ui.chooser_panel.AppHelper", create=True)
    def test_stale_generation_ignored(self, _mock_apphelper):
        """Async results for an old generation are silently discarded."""
        panel = self._make_panel()
        panel._search_generation = 1
        panel._pending_async_count = 1

        merge_calls = []
        original_merge = panel._merge_async_results

        def capture_merge(*args, **kwargs):
            merge_calls.append(args)
            original_merge(*args, **kwargs)

        panel._merge_async_results = capture_merge

        async def search(query):
            await asyncio.sleep(0.05)
            return [ChooserItem(title="old-result")]

        src = ChooserSource(
            name="async-src",
            search=search,
            is_async=True,
        )

        with patch(
            "PyObjCTools.AppHelper.callAfter",
            side_effect=lambda fn, *a, **kw: fn(*a, **kw),
        ):
            panel._launch_async_search(src, "hello", generation=1)
            # Simulate user typing again before result arrives
            panel._search_generation = 2
            assert _wait_for(lambda: len(merge_calls) > 0, timeout=5.0)

        # Results discarded because generation changed
        assert len(panel._current_items) == 0


# ---------------------------------------------------------------------------
# Async demo plugin — source registration
# ---------------------------------------------------------------------------

class TestAsyncDemoSourceRegistration:
    def test_async_source_registered(self):
        from wenzi.scripting.api import _WZNamespace
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        wz = _WZNamespace(reg)
        _ = wz.chooser
        wz.chooser._ensure_command_source()

        from async_demo import setup
        setup(wz)

        assert "async-search" in wz.chooser.panel._sources
        src = wz.chooser.panel._sources["async-search"]
        assert src.is_async is True
        assert src.prefix == "as"
        assert src.search_timeout == 3.0

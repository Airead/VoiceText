"""Tests for scripting async callback utilities."""

import asyncio
import threading
import time

import pytest

from wenzi.scripting.api._async_util import (
    ScriptTaskTracker,
    _submit_and_log,
    wrap_async,
)


def _poll_caplog(caplog, pattern, timeout=2.0):
    """Poll caplog until a record matching *pattern* appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(pattern in r.message for r in caplog.records):
            return
        time.sleep(0.005)
    raise AssertionError(f"Expected log containing {pattern!r} not found within {timeout}s")


class TestWrapAsync:
    """Tests for wrap_async()."""

    def test_sync_callback_unchanged(self):
        """A plain sync callback should work normally."""
        results = []
        cb = wrap_async(lambda: results.append(1))
        cb()
        assert results == [1]

    def test_sync_callback_with_args(self):
        """Sync callback receives arguments."""
        results = []
        cb = wrap_async(lambda x, y: results.append(x + y))
        cb(2, 3)
        assert results == [5]

    def test_sync_callback_return_value(self):
        """Sync callback return value is preserved."""
        cb = wrap_async(lambda: 42)
        assert cb() == 42

    def test_async_def_callback(self):
        """An async def callback should be submitted to the event loop."""
        done = threading.Event()
        results = []

        async def my_async():
            await asyncio.sleep(0.01)
            results.append("async_done")
            done.set()

        cb = wrap_async(my_async)
        # Should not raise, should return None
        ret = cb()
        assert ret is None
        done.wait(timeout=5.0)
        assert results == ["async_done"]

    def test_async_def_with_args(self):
        """An async def callback receives arguments."""
        done = threading.Event()
        results = []

        async def my_async(x, y):
            await asyncio.sleep(0.01)
            results.append(x + y)
            done.set()

        cb = wrap_async(my_async)
        cb(10, 20)
        done.wait(timeout=5.0)
        assert results == [30]

    def test_lambda_returning_coroutine(self):
        """A lambda that returns a coroutine should also be handled."""
        done = threading.Event()
        results = []

        async def my_async():
            await asyncio.sleep(0.01)
            results.append("lambda_coro")
            done.set()

        # This is the common pitfall: lambda: my_async()
        cb = wrap_async(lambda: my_async())
        cb()
        done.wait(timeout=5.0)
        assert results == ["lambda_coro"]

    def test_async_exception_logged(self, caplog):
        """Exceptions in async callbacks should be logged, not silenced."""
        done = threading.Event()

        async def bad_async():
            done.set()
            raise ValueError("test error from async")

        cb = wrap_async(bad_async)
        cb()
        done.wait(timeout=5.0)
        _poll_caplog(caplog, "test error from async")

    def test_sync_exception_not_caught(self):
        """Sync callback exceptions should propagate normally."""

        def bad_sync():
            raise RuntimeError("sync boom")

        cb = wrap_async(bad_sync)
        with pytest.raises(RuntimeError, match="sync boom"):
            cb()

    def test_preserves_function_name(self):
        """Wrapped function should preserve __name__."""

        async def my_named_func():
            pass

        cb = wrap_async(my_named_func)
        assert cb.__name__ == "my_named_func"

    def test_preserves_sync_function_name(self):
        """Wrapped sync function should preserve __name__."""

        def my_sync_func():
            pass

        cb = wrap_async(my_sync_func)
        assert cb.__name__ == "my_sync_func"


class TestSubmitAndLog:
    """Tests for _submit_and_log()."""

    def test_runs_coroutine(self):
        """Coroutine submitted via _submit_and_log should execute."""
        done = threading.Event()
        results = []

        async def coro():
            results.append("ran")
            done.set()

        _submit_and_log(coro())
        done.wait(timeout=5.0)
        assert results == ["ran"]

    def test_logs_exception(self, caplog):
        """Unhandled exception in coroutine should be logged."""
        done = threading.Event()

        async def bad_coro():
            done.set()
            raise TypeError("bad type")

        _submit_and_log(bad_coro())
        done.wait(timeout=5.0)
        _poll_caplog(caplog, "bad type")


class TestScriptTaskTracker:
    """Tests for ScriptTaskTracker."""

    def test_track_and_cancel(self):
        """Tracked tasks should be cancellable."""
        tracker = ScriptTaskTracker()
        cancel_hit = threading.Event()

        import wenzi.async_loop as _aloop

        loop = _aloop.get_loop()

        async def long_running():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                cancel_hit.set()
                raise

        asyncio.run_coroutine_threadsafe(long_running(), loop)

        # Give the task a moment to start
        time.sleep(0.01)

        # Find and track the task
        def _find_and_track():
            for t in asyncio.all_tasks(loop):
                coro = t.get_coro()
                if coro and hasattr(coro, '__name__') and coro.__name__ == 'long_running':
                    tracker.track(t)
                    return

        loop.call_soon_threadsafe(_find_and_track)
        time.sleep(0.01)

        tracker.cancel_all(grace_timeout=2.0)
        cancel_hit.wait(timeout=5.0)
        assert cancel_hit.is_set()

    def test_cancel_empty_noop(self):
        """cancel_all on empty tracker should not raise."""
        tracker = ScriptTaskTracker()
        tracker.cancel_all()

    def test_completed_tasks_auto_removed(self):
        """Tasks that complete normally are removed from tracking."""
        tracker = ScriptTaskTracker()

        import wenzi.async_loop as _aloop

        loop = _aloop.get_loop()

        async def quick():
            return 42

        asyncio.run_coroutine_threadsafe(quick(), loop)

        time.sleep(0.01)

        def _find_and_track():
            for t in asyncio.all_tasks(loop):
                coro = t.get_coro()
                if coro and hasattr(coro, '__name__') and coro.__name__ == 'quick':
                    tracker.track(t)

        loop.call_soon_threadsafe(_find_and_track)
        time.sleep(0.02)

        # Task completed, should be auto-removed
        assert len(tracker._tasks) == 0


class TestWrapAsyncIntegration:
    """Integration tests with real wz APIs."""

    def test_hotkey_bind_async(self):
        """wz.hotkey.bind should accept async callbacks."""
        from wenzi.scripting.api import _WZNamespace
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        wz = _WZNamespace(reg)

        async def my_handler():
            pass

        wz.hotkey.bind("ctrl+cmd+t", my_handler)
        assert len(reg.hotkeys) == 1
        # The stored callback should be a wrapped version
        binding = reg.hotkeys[0]
        assert binding.callback is not my_handler
        assert callable(binding.callback)

    def test_timer_after_async(self):
        """wz.timer.after should accept async callbacks."""
        from wenzi.scripting.api.timer import TimerAPI
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        api = TimerAPI(reg)
        done = threading.Event()
        results = []

        async def cb():
            await asyncio.sleep(0.01)
            results.append("timer_async")
            done.set()

        api.after(0.05, cb)
        done.wait(timeout=5.0)
        assert results == ["timer_async"]

    def test_timer_every_async(self):
        """wz.timer.every should accept async callbacks."""
        from wenzi.scripting.api.timer import TimerAPI
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        api = TimerAPI(reg)
        done = threading.Event()
        results = []

        async def cb():
            results.append(1)
            if len(results) >= 2:
                done.set()

        tid = api.every(0.05, cb)
        done.wait(timeout=5.0)
        api.cancel(tid)
        assert len(results) >= 2

    def test_leader_async_func(self):
        """wz.leader mappings should accept async func."""
        from wenzi.scripting.api import _WZNamespace
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        wz = _WZNamespace(reg)

        async def my_func():
            pass

        wz.leader("cmd_r", [
            {"key": "a", "desc": "test", "func": my_func},
        ])

        mapping = reg.leaders["cmd_r"].mappings[0]
        # func should be wrapped
        assert mapping.func is not my_func
        assert callable(mapping.func)

    def test_on_event_async(self):
        """wz.on() should accept async event handlers."""
        from wenzi.scripting.api import _WZNamespace
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        wz = _WZNamespace(reg)

        done = threading.Event()
        results = []

        @wz.on("test_event")
        async def handler(data):
            results.append(data)
            done.set()

        reg.fire_event("test_event", msg="hello")
        done.wait(timeout=5.0)
        assert len(results) == 1
        assert results[0]["msg"] == "hello"

    def test_wz_run(self):
        """wz.run() should execute a coroutine."""
        from wenzi.scripting.api import _WZNamespace
        from wenzi.scripting.registry import ScriptingRegistry

        reg = ScriptingRegistry()
        wz = _WZNamespace(reg)

        done = threading.Event()
        results = []

        async def my_coro():
            await asyncio.sleep(0.01)
            results.append("ran")
            done.set()

        wz.run(my_coro())
        done.wait(timeout=5.0)
        assert results == ["ran"]

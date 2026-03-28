"""Integration tests for screenshot wiring in config.py and app.py.

These tests verify:
- DEFAULT_CONFIG contains the screenshot section with expected defaults
- _on_screenshot creates overlay and annotation objects
- _on_screenshot_done cleans up properly
- _on_screenshot_cancel cleans up properly

All screenshot module classes and AppKit/Quartz APIs are mocked.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch, call


import pytest


# ---------------------------------------------------------------------------
# Config tests — no heavy mocking needed
# ---------------------------------------------------------------------------


def test_default_config_has_screenshot_section():
    from wenzi.config import DEFAULT_CONFIG

    assert "screenshot" in DEFAULT_CONFIG


def test_default_config_screenshot_hotkey():
    from wenzi.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["screenshot"]["hotkey"] == "cmd+shift+a"


def test_default_config_screenshot_save_directory():
    from wenzi.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["screenshot"]["save_directory"] == "~/Desktop"


def test_default_config_screenshot_sound_enabled():
    from wenzi.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["screenshot"]["sound_enabled"] is True


# ---------------------------------------------------------------------------
# App method tests — mock the app class without instantiating it
# ---------------------------------------------------------------------------


class _FakeApp:
    """Minimal stand-in for WenZiApp that only has the screenshot methods."""

    def __init__(self):
        self._screenshot_overlay = None
        self._screenshot_annotation = None


def _attach_methods(obj):
    """Bind the real screenshot methods from WenZiApp onto a fake instance."""
    import types
    from wenzi import app as app_module

    for name in ("_on_screenshot", "_on_screenshot_done", "_on_screenshot_cancel"):
        method = getattr(app_module.WenZiApp, name)
        setattr(obj, name, types.MethodType(method, obj))


@pytest.fixture()
def fake_app():
    """Return a _FakeApp with screenshot methods bound to it."""
    obj = _FakeApp()
    _attach_methods(obj)
    return obj


@pytest.fixture()
def mock_screenshot_module():
    """Patch wenzi.screenshot so no real AppKit/ScreenCaptureKit code runs."""
    mock_overlay = MagicMock()
    mock_annotation = MagicMock()
    mock_capture_result = MagicMock(name="ScreenData")

    mock_module = MagicMock()
    mock_module.capture_screen.return_value = mock_capture_result
    mock_module.ScreenshotOverlay.return_value = mock_overlay
    mock_module.AnnotationLayer.return_value = mock_annotation

    with patch.dict(sys.modules, {"wenzi.screenshot": mock_module}):
        yield {
            "module": mock_module,
            "overlay": mock_overlay,
            "annotation": mock_annotation,
            "screen_data": mock_capture_result,
        }


def test_on_screenshot_creates_overlay_and_annotation(fake_app, mock_screenshot_module):
    """_on_screenshot should instantiate ScreenshotOverlay and AnnotationLayer."""
    mocks = mock_screenshot_module
    mod = mocks["module"]

    fake_app._on_screenshot()

    mod.capture_screen.assert_called_once()
    mod.ScreenshotOverlay.assert_called_once_with(mocks["screen_data"])
    mod.AnnotationLayer.assert_called_once()
    mocks["overlay"].show.assert_called_once()


def test_on_screenshot_stores_instances(fake_app, mock_screenshot_module):
    """After _on_screenshot, the overlay and annotation are stored on the app."""
    mocks = mock_screenshot_module

    fake_app._on_screenshot()

    assert fake_app._screenshot_overlay is mocks["overlay"]
    assert fake_app._screenshot_annotation is mocks["annotation"]


def test_on_screenshot_capture_failure_logs_and_returns(fake_app, mock_screenshot_module):
    """If capture_screen raises, _on_screenshot should log and not crash."""
    mocks = mock_screenshot_module
    mocks["module"].capture_screen.side_effect = RuntimeError("no screen")

    # Should not raise
    with patch("wenzi.app.logger") as mock_logger:
        fake_app._on_screenshot()
        mock_logger.exception.assert_called_once()

    # No overlay or annotation should be created
    mocks["module"].ScreenshotOverlay.assert_not_called()
    mocks["module"].AnnotationLayer.assert_not_called()


def test_on_screenshot_done_clears_annotation_and_overlay(fake_app):
    """_on_screenshot_done should close the annotation and clear both refs."""
    mock_ann = MagicMock()
    fake_app._screenshot_annotation = mock_ann
    fake_app._screenshot_overlay = MagicMock()  # overlay is not closed by done

    fake_app._on_screenshot_done()

    mock_ann.close.assert_called_once()
    assert fake_app._screenshot_annotation is None
    assert fake_app._screenshot_overlay is None


def test_on_screenshot_done_no_annotation_is_safe(fake_app):
    """_on_screenshot_done with no annotation should not raise."""
    fake_app._screenshot_annotation = None
    fake_app._screenshot_overlay = MagicMock()

    fake_app._on_screenshot_done()  # must not raise

    assert fake_app._screenshot_overlay is None


def test_on_screenshot_cancel_closes_annotation_and_overlay(fake_app):
    """_on_screenshot_cancel should close both annotation and overlay."""
    mock_ann = MagicMock()
    mock_ov = MagicMock()
    fake_app._screenshot_annotation = mock_ann
    fake_app._screenshot_overlay = mock_ov

    fake_app._on_screenshot_cancel()

    mock_ann.close.assert_called_once()
    mock_ov.close.assert_called_once()
    assert fake_app._screenshot_annotation is None
    assert fake_app._screenshot_overlay is None


def test_on_screenshot_cancel_no_objects_is_safe(fake_app):
    """_on_screenshot_cancel with no objects set should not raise."""
    fake_app._screenshot_annotation = None
    fake_app._screenshot_overlay = None

    fake_app._on_screenshot_cancel()  # must not raise


def test_on_screenshot_cancel_only_annotation_set(fake_app):
    """_on_screenshot_cancel handles the case where only annotation is set."""
    mock_ann = MagicMock()
    fake_app._screenshot_annotation = mock_ann
    fake_app._screenshot_overlay = None

    fake_app._on_screenshot_cancel()

    mock_ann.close.assert_called_once()
    assert fake_app._screenshot_annotation is None
    assert fake_app._screenshot_overlay is None

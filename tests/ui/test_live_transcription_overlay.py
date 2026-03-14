"""Tests for the live transcription overlay."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import mock_panel_close_delegate


@pytest.fixture(autouse=True)
def _mock_appkit(mock_appkit_modules, monkeypatch):
    """Mock AppKit and Foundation modules for headless testing."""
    import voicetext.ui.live_transcription_overlay as _lt

    _lt._PanelCloseDelegate = None
    mock_panel_close_delegate(monkeypatch, _lt)
    return mock_appkit_modules


class TestLiveTranscriptionOverlayInit:
    def test_defaults(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        assert overlay._panel is None
        assert overlay._text_field is None
        assert not overlay.is_visible

    def test_show_creates_panel(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        assert overlay._panel is not None
        assert overlay._text_field is not None

    def test_show_sets_panel_properties(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        panel = overlay._panel
        panel.setFloatingPanel_.assert_called_with(True)
        panel.setHidesOnDeactivate_.assert_called_with(False)
        panel.setIgnoresMouseEvents_.assert_called_with(True)
        panel.setOpaque_.assert_called_with(False)


class TestLiveTranscriptionOverlayText:
    @staticmethod
    def _setup_frame_mock(overlay):
        """Set up proper numeric frame mocks for text field and panel."""
        text_frame = MagicMock()
        text_frame.size.height = 30.0
        overlay._text_field.frame.return_value = text_frame

        panel_frame = MagicMock()
        panel_frame.size.height = 60.0
        panel_frame.origin.y = 400.0
        overlay._panel.frame.return_value = panel_frame

    def test_update_text(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        self._setup_frame_mock(overlay)

        overlay.update_text("hello world")

        assert overlay._current_text == "hello world"
        overlay._text_field.setStringValue_.assert_called_with("hello world")

    def test_update_text_noop_without_show(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        # Should not raise
        overlay.update_text("hello")

    def test_update_text_auto_resizes(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        self._setup_frame_mock(overlay)

        overlay.update_text("some text")

        overlay._text_field.sizeToFit.assert_called()
        overlay._panel.setFrame_display_.assert_called()


class TestLiveTranscriptionOverlayLifecycle:
    def test_hide(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        panel = overlay._panel

        overlay.hide()

        panel.orderOut_.assert_called()

    def test_close_cleans_up(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        overlay.close()

        assert overlay._panel is None
        assert overlay._text_field is None
        assert overlay._current_text == ""

    def test_close_without_show(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        # Should not raise
        overlay.close()

    def test_show_after_close(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        overlay.close()
        overlay.show()

        assert overlay._panel is not None


class TestLiveTranscriptionOverlayDarkMode:
    def test_dynamic_color_used_for_background(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        # Background color should be set (dynamic color provider)
        overlay._panel.setBackgroundColor_.assert_called_once()

    def test_label_color_for_text(self):
        from AppKit import NSColor
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        overlay._text_field.setTextColor_.assert_called_once_with(NSColor.labelColor())

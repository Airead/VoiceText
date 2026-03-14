"""Tests for the live transcription overlay."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_appkit(mock_appkit_modules, monkeypatch):
    """Mock AppKit and Foundation modules for headless testing."""
    return mock_appkit_modules


class TestLiveTranscriptionOverlayInit:
    def test_defaults(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        assert overlay._panel is None
        assert overlay._text_field is None
        assert overlay._screen_center_y == 0

    def test_show_creates_panel(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        assert overlay._panel is not None
        assert overlay._text_field is not None
        assert overlay._content_view is not None

    def test_show_sets_panel_properties(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        panel = overlay._panel
        panel.setHidesOnDeactivate_.assert_called_with(False)
        panel.setIgnoresMouseEvents_.assert_called_with(True)
        panel.setOpaque_.assert_called_with(False)
        panel.setHasShadow_.assert_called_with(True)

    def test_show_uses_clear_panel_background(self):
        from AppKit import NSColor
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        overlay._panel.setBackgroundColor_.assert_called_once_with(
            NSColor.clearColor()
        )


class TestLiveTranscriptionOverlayText:
    @staticmethod
    def _setup_frame_mock(overlay):
        """Set up proper numeric frame mocks for text field and panel."""
        # Mock cellSizeForBounds_ for _resize_panel
        cell_mock = MagicMock()
        needed_size = MagicMock()
        needed_size.height = 30.0
        cell_mock.cellSizeForBounds_.return_value = needed_size
        overlay._text_field.cell.return_value = cell_mock

        panel_frame = MagicMock()
        panel_frame.size.height = 40.0
        panel_frame.origin.y = 400.0
        panel_frame.origin.x = 200.0
        overlay._panel.frame.return_value = panel_frame

    def test_update_text(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        self._setup_frame_mock(overlay)

        overlay.update_text("hello world")

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

        # Make height differ enough to trigger resize
        cell_mock = overlay._text_field.cell()
        needed = MagicMock()
        needed.height = 60.0
        cell_mock.cellSizeForBounds_.return_value = needed

        overlay.update_text("some text")

        overlay._panel.setFrame_display_.assert_called()


class TestLiveTranscriptionOverlayLifecycle:
    def test_hide(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()
        panel = overlay._panel

        overlay.hide()

        panel.orderOut_.assert_called()
        assert overlay._panel is None
        assert overlay._text_field is None
        assert overlay._content_view is None

    def test_close_cleans_up(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        overlay.close()

        assert overlay._panel is None
        assert overlay._content_view is None
        assert overlay._text_field is None

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
    def test_layer_background_set(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        # Background color is applied via layer, not panel
        content = overlay._content_view
        content.setWantsLayer_.assert_called_with(True)

    def test_text_uses_dynamic_color(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        # Text color should be set (dynamic, not hardcoded)
        overlay._text_field.setTextColor_.assert_called_once()

    def test_text_center_aligned(self):
        from voicetext.ui.live_transcription_overlay import LiveTranscriptionOverlay

        overlay = LiveTranscriptionOverlay()
        overlay.show()

        overlay._text_field.setAlignment_.assert_called_once_with(1)

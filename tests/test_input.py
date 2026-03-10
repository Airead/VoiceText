"""Tests for the text input module."""

from unittest.mock import patch, MagicMock

from voicetext.input import type_text


class TestTypeText:
    def test_empty_text_does_nothing(self):
        with patch("voicetext.input._type_via_clipboard") as mock_clip:
            type_text("")
            mock_clip.assert_not_called()

    @patch("voicetext.input._type_via_clipboard", return_value=True)
    def test_auto_tries_clipboard_first(self, mock_clip):
        type_text("hello", method="auto")
        mock_clip.assert_called_once_with("hello")

    @patch("voicetext.input._type_via_clipboard", return_value=False)
    @patch("voicetext.input._type_via_applescript", return_value=True)
    def test_auto_falls_back_to_applescript(self, mock_apple, mock_clip):
        type_text("hello", method="auto")
        mock_clip.assert_called_once()
        mock_apple.assert_called_once()

    @patch("voicetext.input._type_via_clipboard", return_value=True)
    def test_append_newline(self, mock_clip):
        type_text("hello", append_newline=True)
        mock_clip.assert_called_once_with("hello\n")

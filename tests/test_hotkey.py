"""Tests for the hotkey module."""

import pytest
from unittest.mock import MagicMock, patch

from voicetext.hotkey import _parse_key, HoldHotkeyListener


class TestParseKey:
    def test_special_key(self):
        from pynput import keyboard
        assert _parse_key("f2") == keyboard.Key.f2
        assert _parse_key("cmd") == keyboard.Key.cmd

    def test_char_key(self):
        from pynput import keyboard
        result = _parse_key("a")
        assert isinstance(result, keyboard.KeyCode)

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown key"):
            _parse_key("nonexistent")

    def test_case_insensitive(self):
        from pynput import keyboard
        assert _parse_key("F2") == keyboard.Key.f2


class TestHoldHotkeyListener:
    def test_press_and_release_callbacks(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HoldHotkeyListener("f2", on_press, on_release)

        from pynput import keyboard
        # Simulate press
        listener._handle_press(keyboard.Key.f2)
        on_press.assert_called_once()
        assert listener._held is True

        # Simulate release
        listener._handle_release(keyboard.Key.f2)
        on_release.assert_called_once()
        assert listener._held is False

    def test_repeated_press_ignored(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HoldHotkeyListener("f2", on_press, on_release)

        from pynput import keyboard
        listener._handle_press(keyboard.Key.f2)
        listener._handle_press(keyboard.Key.f2)  # Repeated, should be ignored
        assert on_press.call_count == 1

    def test_wrong_key_ignored(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HoldHotkeyListener("f2", on_press, on_release)

        from pynput import keyboard
        listener._handle_press(keyboard.Key.f3)
        on_press.assert_not_called()

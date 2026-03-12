"""Tests for the hotkey module."""

import pytest
from unittest.mock import MagicMock, patch

from voicetext.hotkey import (
    _parse_key,
    _is_fn_key,
    _convert_hotkey_to_pynput,
    _QuartzFnListener,
    _PynputListener,
    HoldHotkeyListener,
    TapHotkeyListener,
)


class TestParseKey:
    def test_special_key(self):
        from pynput import keyboard
        assert _parse_key("f2") == keyboard.Key.f2
        assert _parse_key("cmd") == keyboard.Key.cmd

    def test_fn_key(self):
        from pynput import keyboard
        result = _parse_key("fn")
        assert isinstance(result, keyboard.KeyCode)
        assert result.vk == 0x3F

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


class TestIsFnKey:
    def test_fn_variants(self):
        assert _is_fn_key("fn") is True
        assert _is_fn_key("FN") is True
        assert _is_fn_key(" fn ") is True

    def test_non_fn(self):
        assert _is_fn_key("f2") is False
        assert _is_fn_key("cmd") is False


class TestHoldHotkeyListener:
    def test_fn_uses_quartz_backend(self):
        listener = HoldHotkeyListener("fn", MagicMock(), MagicMock())
        assert isinstance(listener._impl, _QuartzFnListener)

    def test_regular_key_uses_pynput_backend(self):
        listener = HoldHotkeyListener("f2", MagicMock(), MagicMock())
        assert isinstance(listener._impl, _PynputListener)

    def test_pynput_press_and_release(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HoldHotkeyListener("f2", on_press, on_release)

        from pynput import keyboard
        listener._impl._handle_press(keyboard.Key.f2)
        on_press.assert_called_once()
        assert listener._impl._held is True

        listener._impl._handle_release(keyboard.Key.f2)
        on_release.assert_called_once()
        assert listener._impl._held is False

    def test_pynput_repeated_press_ignored(self):
        on_press = MagicMock()
        listener = HoldHotkeyListener("f2", on_press, MagicMock())

        from pynput import keyboard
        listener._impl._handle_press(keyboard.Key.f2)
        listener._impl._handle_press(keyboard.Key.f2)
        assert on_press.call_count == 1

    def test_pynput_wrong_key_ignored(self):
        on_press = MagicMock()
        listener = HoldHotkeyListener("f2", on_press, MagicMock())

        from pynput import keyboard
        listener._impl._handle_press(keyboard.Key.f3)
        on_press.assert_not_called()


class TestConvertHotkeyToPynput:
    def test_simple_combo(self):
        assert _convert_hotkey_to_pynput("ctrl+shift+v") == "<ctrl>+<shift>+v"

    def test_cmd(self):
        assert _convert_hotkey_to_pynput("cmd+c") == "<cmd>+c"

    def test_option_maps_to_alt(self):
        assert _convert_hotkey_to_pynput("option+shift+e") == "<alt>+<shift>+e"

    def test_command_maps_to_cmd(self):
        assert _convert_hotkey_to_pynput("command+v") == "<cmd>+v"

    def test_strips_spaces(self):
        assert _convert_hotkey_to_pynput(" ctrl + shift + v ") == "<ctrl>+<shift>+v"

    def test_case_insensitive(self):
        assert _convert_hotkey_to_pynput("Ctrl+Shift+V") == "<ctrl>+<shift>+v"


class TestTapHotkeyListener:
    def test_creation(self):
        cb = MagicMock()
        listener = TapHotkeyListener("ctrl+shift+v", cb)
        assert listener._pynput_hotkey == "<ctrl>+<shift>+v"
        assert listener._on_activate is cb

    def test_stop_when_not_started(self):
        listener = TapHotkeyListener("ctrl+v", MagicMock())
        listener.stop()
        assert listener._listener is None

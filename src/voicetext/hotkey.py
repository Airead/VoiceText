"""Global hotkey listener for press-and-hold interaction."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from pynput import keyboard


logger = logging.getLogger(__name__)

_SPECIAL_KEYS = {
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
    "esc": keyboard.Key.esc,
    "space": keyboard.Key.space,
    "cmd": keyboard.Key.cmd,
    "ctrl": keyboard.Key.ctrl,
    "alt": keyboard.Key.alt,
    "option": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
}


def _parse_key(name: str):
    """Parse a key name string to a pynput key object."""
    name = name.strip().lower()
    if name in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[name]
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown key: {name}")


class HoldHotkeyListener:
    """Listen for a hotkey: call on_press when pressed, on_release when released."""

    def __init__(
        self,
        key_name: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self._target_key = _parse_key(key_name)
        self._on_press = on_press
        self._on_release = on_release
        self._listener: Optional[keyboard.Listener] = None
        self._held = False

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started, key=%s", self._target_key)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped")

    def _normalize(self, key):
        if isinstance(key, keyboard.Key):
            return key
        if isinstance(key, keyboard.KeyCode):
            if key.vk is not None:
                return key.vk
            if key.char is not None:
                return keyboard.KeyCode.from_char(key.char.lower())
        return key

    def _matches(self, key) -> bool:
        normalized = self._normalize(key)
        target = self._normalize(self._target_key)
        return normalized == target

    def _handle_press(self, key) -> None:
        if self._matches(key) and not self._held:
            self._held = True
            try:
                self._on_press()
            except Exception as e:
                logger.error("on_press callback error: %s", e)

    def _handle_release(self, key) -> None:
        if self._matches(key) and self._held:
            self._held = False
            try:
                self._on_release()
            except Exception as e:
                logger.error("on_release callback error: %s", e)

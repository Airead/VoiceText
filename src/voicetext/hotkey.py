"""Global hotkey listener for press-and-hold interaction."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from pynput import keyboard


logger = logging.getLogger(__name__)

_FN_FLAG = 0x800000  # NSEventModifierFlagFunction
_FN_KEYCODE = 63

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
    "fn": keyboard.KeyCode.from_vk(_FN_KEYCODE),
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


def _is_fn_key(name: str) -> bool:
    return name.strip().lower() == "fn"


class _QuartzFnListener:
    """Listen for fn key press/release via Quartz event tap."""

    def __init__(
        self,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._held = False
        self._tap = None
        self._loop = None
        self._thread: Optional[threading.Thread] = None

    def _callback(self, proxy, event_type, event, refcon):
        import Quartz
        from AppKit import NSEvent

        logger.debug(
            "Quartz event: type=%s", event_type
        )

        if event_type != Quartz.kCGEventFlagsChanged:
            return event

        ns_event = NSEvent.eventWithCGEvent_(event)
        if ns_event is None:
            logger.debug("Quartz: ns_event is None")
            return event

        keycode = ns_event.keyCode()
        flags = ns_event.modifierFlags()
        logger.debug(
            "Quartz flagsChanged: keyCode=%d flags=0x%08x", keycode, flags
        )

        if keycode != _FN_KEYCODE:
            return event

        fn_down = bool(flags & _FN_FLAG)
        logger.debug("fn key event: fn_down=%s held=%s", fn_down, self._held)

        if fn_down and not self._held:
            self._held = True
            try:
                self._on_press()
            except Exception as e:
                logger.error("on_press callback error: %s", e)
        elif not fn_down and self._held:
            self._held = False
            try:
                self._on_release()
            except Exception as e:
                logger.error("on_release callback error: %s", e)

        return event

    def start(self) -> None:
        import Quartz

        def _run():
            mask = Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            self._tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                self._callback,
                None,
            )
            if self._tap is None:
                logger.error(
                    "Failed to create Quartz event tap for fn key. "
                    "Check accessibility permissions in System Settings."
                )
                return
            logger.debug("Quartz event tap created successfully: %s", self._tap)

            source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
            self._loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(
                self._loop, source, Quartz.kCFRunLoopDefaultMode
            )
            Quartz.CGEventTapEnable(self._tap, True)
            logger.info("Quartz fn key listener started")
            Quartz.CFRunLoopRun()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        import Quartz

        if self._loop is not None:
            Quartz.CFRunLoopStop(self._loop)
            self._loop = None
        self._tap = None
        logger.info("Quartz fn key listener stopped")


class _PynputListener:
    """Listen for a regular key via pynput."""

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
        logger.info("Pynput hotkey listener started, key=%s", self._target_key)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Pynput hotkey listener stopped")

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


def _convert_hotkey_to_pynput(hotkey_str: str) -> str:
    """Convert user hotkey format to pynput GlobalHotKeys format.

    Examples:
        "ctrl+shift+v" -> "<ctrl>+<shift>+v"
        "cmd+c" -> "<cmd>+c"
    """
    parts = hotkey_str.strip().lower().split("+")
    converted = []
    modifiers = {"ctrl", "shift", "alt", "option", "cmd", "command"}
    for part in parts:
        part = part.strip()
        if part in modifiers:
            if part == "option":
                part = "alt"
            elif part == "command":
                part = "cmd"
            converted.append(f"<{part}>")
        else:
            converted.append(part)
    return "+".join(converted)


class TapHotkeyListener:
    """Listen for a hotkey combination (single tap, not hold).

    Uses pynput's GlobalHotKeys to listen for key combinations like
    "ctrl+shift+v" and fire the callback once per activation.
    """

    def __init__(self, hotkey_str: str, on_activate: Callable[[], None]) -> None:
        self._hotkey_str = hotkey_str
        self._on_activate = on_activate
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._pynput_hotkey = _convert_hotkey_to_pynput(hotkey_str)

    def start(self) -> None:
        self._listener = keyboard.GlobalHotKeys({
            self._pynput_hotkey: self._on_activate,
        })
        self._listener.daemon = True
        self._listener.start()
        logger.info(
            "TapHotkeyListener started: %s -> %s",
            self._hotkey_str, self._pynput_hotkey,
        )

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("TapHotkeyListener stopped")


class HoldHotkeyListener:
    """Listen for a hotkey: call on_press when pressed, on_release when released.

    Uses Quartz event tap for fn key (not supported by pynput),
    and pynput for all other keys.
    """

    def __init__(
        self,
        key_name: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        if _is_fn_key(key_name):
            self._impl = _QuartzFnListener(on_press, on_release)
        else:
            self._impl = _PynputListener(key_name, on_press, on_release)

    def start(self) -> None:
        self._impl.start()

    def stop(self) -> None:
        self._impl.stop()

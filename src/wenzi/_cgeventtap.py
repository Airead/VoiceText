"""Low-level ctypes bindings for CGEventTap — no PyObjC bridge.

Using ctypes instead of PyObjC for CGEventTapCreate avoids the PyObjC
callback bridge retaining CGEventRef wrappers indefinitely.
"""
from __future__ import annotations

import ctypes
import ctypes.util
from ctypes import CFUNCTYPE, c_bool, c_int32, c_int64, c_uint32, c_uint64, c_void_p

# ---------------------------------------------------------------------------
# Load frameworks
# ---------------------------------------------------------------------------
_cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
_cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

# ---------------------------------------------------------------------------
# Callback type
# ---------------------------------------------------------------------------
CGEventTapCallBack = CFUNCTYPE(c_void_p, c_void_p, c_uint32, c_void_p, c_void_p)

# ---------------------------------------------------------------------------
# Constants (hardcoded — no Quartz import)
# ---------------------------------------------------------------------------
kCGSessionEventTap = 1
kCGHeadInsertEventTap = 0

kCGEventTapOptionDefault = 0
kCGEventTapOptionListenOnly = 1

kCGEventKeyDown = 10
kCGEventKeyUp = 11
kCGEventFlagsChanged = 12

kCGEventTapDisabledByTimeout = 0xFFFFFFFE

kCGKeyboardEventKeycode = 9

kCGAnnotatedSessionEventTap = 2

kCGEventSourceStateCombinedSessionState = 0

kCGEventFlagMaskCommand = 1 << 20
kCGEventFlagMaskControl = 1 << 18
kCGEventFlagMaskAlternate = 1 << 19
kCGEventFlagMaskShift = 1 << 17

kCFRunLoopDefaultMode = c_void_p.in_dll(_cf, "kCFRunLoopDefaultMode")

# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

# CGEventTapCreate(tap, place, options, eventsOfInterest, callback, userInfo)
_cg.CGEventTapCreate.restype = c_void_p
_cg.CGEventTapCreate.argtypes = [
    c_uint32,           # CGEventTapLocation
    c_uint32,           # CGEventTapPlacement
    c_uint32,           # CGEventTapOptions
    c_uint64,           # CGEventMask
    CGEventTapCallBack, # callback
    c_void_p,           # userInfo
]

# CGEventTapEnable(tap, enable)
_cg.CGEventTapEnable.restype = None
_cg.CGEventTapEnable.argtypes = [c_void_p, c_bool]

# CGEventGetIntegerValueField(event, field) -> int64
_cg.CGEventGetIntegerValueField.restype = c_int64
_cg.CGEventGetIntegerValueField.argtypes = [c_void_p, c_uint32]

# CGEventGetFlags(event) -> uint64
_cg.CGEventGetFlags.restype = c_uint64
_cg.CGEventGetFlags.argtypes = [c_void_p]

# CGEventSetFlags(event, flags)
_cg.CGEventSetFlags.restype = None
_cg.CGEventSetFlags.argtypes = [c_void_p, c_uint64]

# CGEventSourceFlagsState(stateID) -> uint64
_cg.CGEventSourceFlagsState.restype = c_uint64
_cg.CGEventSourceFlagsState.argtypes = [c_int32]

# CGEventCreateKeyboardEvent(source, virtualKey, keyDown) -> CGEventRef
_cg.CGEventCreateKeyboardEvent.restype = c_void_p
_cg.CGEventCreateKeyboardEvent.argtypes = [c_void_p, c_uint32, c_bool]

# CGEventPost(tap, event)
_cg.CGEventPost.restype = None
_cg.CGEventPost.argtypes = [c_uint32, c_void_p]

# CFMachPortCreateRunLoopSource(allocator, port, order) -> CFRunLoopSourceRef
_cf.CFMachPortCreateRunLoopSource.restype = c_void_p
_cf.CFMachPortCreateRunLoopSource.argtypes = [c_void_p, c_void_p, c_int64]

# CFRunLoopGetCurrent() -> CFRunLoopRef
_cf.CFRunLoopGetCurrent.restype = c_void_p
_cf.CFRunLoopGetCurrent.argtypes = []

# CFRunLoopAddSource(rl, source, mode)
_cf.CFRunLoopAddSource.restype = None
_cf.CFRunLoopAddSource.argtypes = [c_void_p, c_void_p, c_void_p]

# CFRunLoopRun()
_cf.CFRunLoopRun.restype = None
_cf.CFRunLoopRun.argtypes = []

# CFRunLoopStop(rl)
_cf.CFRunLoopStop.restype = None
_cf.CFRunLoopStop.argtypes = [c_void_p]

# CFRelease(cf)
_cf.CFRelease.restype = None
_cf.CFRelease.argtypes = [c_void_p]

# ---------------------------------------------------------------------------
# Module-level Python functions
# ---------------------------------------------------------------------------


def CGEventTapCreate(tap, place, options, events_of_interest, callback, user_info):
    return _cg.CGEventTapCreate(tap, place, options, events_of_interest, callback, user_info)


def CGEventTapEnable(tap, enable):
    _cg.CGEventTapEnable(tap, enable)


def CGEventGetIntegerValueField(event, field):
    return _cg.CGEventGetIntegerValueField(event, field)


def CGEventGetFlags(event):
    return _cg.CGEventGetFlags(event)


def CGEventSetFlags(event, flags):
    _cg.CGEventSetFlags(event, flags)


def CGEventSourceFlagsState(state_id):
    return _cg.CGEventSourceFlagsState(state_id)


def CGEventCreateKeyboardEvent(source, virtual_key, key_down):
    return _cg.CGEventCreateKeyboardEvent(source, virtual_key, key_down)


def CGEventPost(tap, event):
    _cg.CGEventPost(tap, event)


def CFMachPortCreateRunLoopSource(allocator, port, order):
    return _cf.CFMachPortCreateRunLoopSource(allocator, port, order)


def CFRunLoopGetCurrent():
    return _cf.CFRunLoopGetCurrent()


def CFRunLoopAddSource(rl, source, mode):
    _cf.CFRunLoopAddSource(rl, source, mode)


def CFRunLoopRun():
    _cf.CFRunLoopRun()


def CFRunLoopStop(rl):
    _cf.CFRunLoopStop(rl)


def CFRelease(cf):
    _cf.CFRelease(cf)


def CGEventMaskBit(event_type):
    """Pure Python implementation of CGEventMaskBit."""
    return 1 << event_type

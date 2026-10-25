"""macOS keycode resolution and global key press detection via Quartz."""

import ctypes

__all__ = ["resolve_keycode", "is_key_pressed"]

kCGEventSourceStateHIDSystemState = 1

# Tk keysym → macOS virtual key code (kVK_* in HIToolbox/Events.h)
_VK_MAP = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06, "x": 0x07,
    "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10,
    "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "equal": 0x18,
    "9": 0x19, "7": 0x1A, "minus": 0x1B, "8": 0x1C, "0": 0x1D, "bracketright": 0x1E, "o": 0x1F,
    "u": 0x20, "bracketleft": 0x21, "i": 0x22, "p": 0x23, "Return": 0x24, "l": 0x25, "j": 0x26,
    "apostrophe": 0x27, "k": 0x28, "semicolon": 0x29, "backslash": 0x2A, "comma": 0x2B,
    "slash": 0x2C, "n": 0x2D, "m": 0x2E, "period": 0x2F, "Tab": 0x30, "space": 0x31,
    "grave": 0x32, "BackSpace": 0x33, "Escape": 0x35, "Shift_L": 0x38, "Caps_Lock": 0x39,
    "Alt_L": 0x3A, "Control_L": 0x3B, "Shift_R": 0x3C, "Alt_R": 0x3D, "Control_R": 0x3E,
    "F17": 0x40, "F18": 0x4F, "F19": 0x50, "F20": 0x5A, "F5": 0x60, "F6": 0x61, "F7": 0x62,
    "F3": 0x63, "F8": 0x64, "F9": 0x65, "F11": 0x67, "F13": 0x69, "F16": 0x6A, "F14": 0x6B,
    "F10": 0x6D, "F12": 0x6F, "F15": 0x71, "Help": 0x72, "Insert": 0x72, "Home": 0x73,
    "Prior": 0x74, "Delete": 0x75, "F4": 0x76, "End": 0x77, "F2": 0x78, "Next": 0x79,
    "F1": 0x7A, "Left": 0x7B, "Right": 0x7C, "Down": 0x7D, "Up": 0x7E,
}

try:
    _cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    _cg.CGEventSourceKeyState.argtypes = [ctypes.c_int32, ctypes.c_uint16]
    _cg.CGEventSourceKeyState.restype = ctypes.c_bool
except OSError:
    _cg = None


def resolve_keycode(key_name):
    if key_name in _VK_MAP:
        return _VK_MAP[key_name]

    return _VK_MAP.get(key_name.lower()) if len(key_name) == 1 else None


def is_key_pressed(keycode):
    if keycode is None or not _cg:
        return False

    return bool(_cg.CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, keycode))

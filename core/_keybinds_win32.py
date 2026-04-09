"""Win32 keycode resolution and global key press detection."""

import ctypes

__all__ = ["resolve_keycode", "is_key_pressed"]

_VK_MAP = {
    "Escape": 0x1B, "Return": 0x0D, "Tab": 0x09, "space": 0x20,
    "BackSpace": 0x08, "Delete": 0x2E, "Insert": 0x2D,
    "Home": 0x24, "End": 0x23, "Prior": 0x21, "Next": 0x22,
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "Shift_L": 0xA0, "Shift_R": 0xA1,
    "Control_L": 0xA2, "Control_R": 0xA3,
    "Alt_L": 0xA4, "Alt_R": 0xA5,
}

for i in range(26):
    _VK_MAP[chr(ord("a") + i)] = 0x41 + i

for i in range(10):
    _VK_MAP[str(i)] = 0x30 + i

try:
    _user32 = ctypes.windll.user32
except AttributeError:
    _user32 = None


def resolve_keycode(key_name):
    return _VK_MAP.get(key_name)


def is_key_pressed(keycode):
    if not keycode or not _user32:
        return False
    state = _user32.GetAsyncKeyState(keycode)
    return bool(state & 0x8000)

"""X11 keycode resolution and global key press detection."""

import ctypes

__all__ = ["resolve_keycode", "is_key_pressed"]

try:
    _xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
    _xlib.XOpenDisplay.restype = ctypes.c_void_p
    _xlib.XStringToKeysym.argtypes = [ctypes.c_char_p]
    _xlib.XStringToKeysym.restype = ctypes.c_ulong
    _xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    _xlib.XKeysymToKeycode.restype = ctypes.c_uint
    _xlib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _xlib.XQueryKeymap.restype = ctypes.c_int

    _display = _xlib.XOpenDisplay(None)
except OSError:
    _xlib = None
    _display = None


def resolve_keycode(key_name):
    if not _display:
        return None
    keysym = _xlib.XStringToKeysym(key_name.encode())
    if keysym == 0:
        return None
    keycode = _xlib.XKeysymToKeycode(_display, keysym)
    return keycode if keycode else None


def is_key_pressed(keycode):
    if not keycode or not _display:
        return False
    keymap = ctypes.create_string_buffer(32)
    _xlib.XQueryKeymap(_display, keymap)
    byte_index = keycode // 8
    bit_mask = 1 << (keycode % 8)
    return bool(keymap.raw[byte_index] & bit_mask)

"""X11 mouse control via ctypes (libX11 + libXtst)."""

import ctypes
import sys

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos", "is_escape_pressed"]

_xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
_xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")

_xlib.XOpenDisplay.restype = ctypes.c_void_p
_xlib.XDefaultRootWindow.restype = ctypes.c_ulong
_xlib.XStringToKeysym.argtypes = [ctypes.c_char_p]
_xlib.XStringToKeysym.restype = ctypes.c_ulong
_xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
_xlib.XKeysymToKeycode.restype = ctypes.c_uint
_xlib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_xlib.XQueryKeymap.restype = ctypes.c_int

_display = _xlib.XOpenDisplay(None)
if not _display:
    print("Error: cannot open X display. Are you running under X11?")
    sys.exit(1)
_root = _xlib.XDefaultRootWindow(_display)
_escape_keysym = _xlib.XStringToKeysym(b"Escape")
_escape_keycode = _xlib.XKeysymToKeycode(_display, _escape_keysym)


def mouse_move(x, y):
    _xlib.XWarpPointer(_display, 0, _root, 0, 0, 0, 0, int(x), int(y))
    _xlib.XFlush(_display)


def mouse_down(button=1):
    _xtst.XTestFakeButtonEvent(_display, int(button), 1, 0)
    _xlib.XFlush(_display)


def mouse_up(button=1):
    _xtst.XTestFakeButtonEvent(_display, int(button), 0, 0)
    _xlib.XFlush(_display)


def get_mouse_pos():
    root_x = ctypes.c_int()
    root_y = ctypes.c_int()
    win_x = ctypes.c_int()
    win_y = ctypes.c_int()
    child = ctypes.c_ulong()
    root_ret = ctypes.c_ulong()
    mask = ctypes.c_uint()
    _xlib.XQueryPointer(
        _display, _root,
        ctypes.byref(root_ret), ctypes.byref(child),
        ctypes.byref(root_x), ctypes.byref(root_y),
        ctypes.byref(win_x), ctypes.byref(win_y),
        ctypes.byref(mask)
    )
    return root_x.value, root_y.value


def is_escape_pressed():
    if not _escape_keycode:
        return False
    keymap = ctypes.create_string_buffer(32)
    _xlib.XQueryKeymap(_display, keymap)
    byte_index = _escape_keycode // 8
    bit_mask = 1 << (_escape_keycode % 8)
    key_value = keymap.raw[byte_index]
    return bool(key_value & bit_mask)

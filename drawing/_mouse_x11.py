"""X11 mouse control via ctypes (libX11 + libXtst)."""

import ctypes
import sys

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

_xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
_xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")

_xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
_xlib.XOpenDisplay.restype = ctypes.c_void_p
_xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
_xlib.XDefaultRootWindow.restype = ctypes.c_ulong
_xlib.XFlush.argtypes = [ctypes.c_void_p]
_xlib.XQueryPointer.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ctypes.POINTER(ctypes.c_uint),
]
_xtst.XTestFakeMotionEvent.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong,
]
_xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]

_display = _xlib.XOpenDisplay(None)
if not _display:
    print("Error: cannot open X display. Are you running under X11?")
    sys.exit(1)
_root = _xlib.XDefaultRootWindow(_display)


def mouse_move(x, y):
    _xtst.XTestFakeMotionEvent(_display, -1, int(x), int(y), 0)
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



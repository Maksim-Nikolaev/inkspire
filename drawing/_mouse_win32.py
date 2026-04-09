"""Win32 mouse control via ctypes (user32.dll)."""

import ctypes
import ctypes.wintypes

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

_user32 = ctypes.windll.user32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
INPUT_MOUSE = 0


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", _U),
    ]


def _send_mouse_event(flags):
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dwFlags = flags
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def mouse_move(x, y):
    _user32.SetCursorPos(int(x), int(y))


def mouse_down(button=1):
    flag = MOUSEEVENTF_LEFTDOWN if button == 1 else MOUSEEVENTF_RIGHTDOWN
    _send_mouse_event(flag)


def mouse_up(button=1):
    flag = MOUSEEVENTF_LEFTUP if button == 1 else MOUSEEVENTF_RIGHTUP
    _send_mouse_event(flag)


def get_mouse_pos():
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

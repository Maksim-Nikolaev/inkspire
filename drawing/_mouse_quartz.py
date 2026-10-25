"""macOS mouse control via ctypes (Quartz CGEvent)."""

import ctypes

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

_cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
_cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

kCGHIDEventTap = 0
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 3
kCGEventRightMouseUp = 4
kCGEventMouseMoved = 5
kCGEventLeftMouseDragged = 6
kCGEventRightMouseDragged = 7
kCGMouseButtonLeft = 0
kCGMouseButtonRight = 1
kCGMouseEventClickState = 1

# button numbers follow X11: 1 = left, 3 = right
_BUTTONS = {
    1: (kCGMouseButtonLeft, kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGEventLeftMouseDragged),
    3: (kCGMouseButtonRight, kCGEventRightMouseDown, kCGEventRightMouseUp, kCGEventRightMouseDragged),
}


class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


_cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
_cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
_cg.CGEventSetIntegerValueField.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
_cg.CGEventSetIntegerValueField.restype = None
_cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
_cg.CGEventPost.restype = None
_cg.CGEventCreate.argtypes = [ctypes.c_void_p]
_cg.CGEventCreate.restype = ctypes.c_void_p
_cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
_cg.CGEventGetLocation.restype = CGPoint
_cf.CFRelease.argtypes = [ctypes.c_void_p]
_cf.CFRelease.restype = None

_held = None
_last = None


def _post(event_type, x, y, cg_button, click_state=False):
    event = _cg.CGEventCreateMouseEvent(None, event_type, CGPoint(float(x), float(y)), cg_button)

    if not event:
        return

    if click_state:
        _cg.CGEventSetIntegerValueField(event, kCGMouseEventClickState, 1)

    _cg.CGEventPost(kCGHIDEventTap, event)
    _cf.CFRelease(event)


def mouse_move(x, y):
    global _last

    _last = (float(x), float(y))

    # Apps only see a stroke when moves made with a button held are sent as "dragged" events.
    if _held is None:
        _post(kCGEventMouseMoved, x, y, kCGMouseButtonLeft)
    else:
        cg_button, _, _, dragged = _BUTTONS[_held]
        _post(dragged, x, y, cg_button)


def mouse_down(button=1):
    global _held

    cg_button, down, _, _ = _BUTTONS.get(button, _BUTTONS[1])
    x, y = _last or get_mouse_pos()
    _held = button if button in _BUTTONS else 1
    _post(down, x, y, cg_button, click_state=True)


def mouse_up(button=1):
    global _held

    cg_button, _, up, _ = _BUTTONS.get(button, _BUTTONS[1])
    x, y = _last or get_mouse_pos()
    _held = None
    _post(up, x, y, cg_button, click_state=True)


def get_mouse_pos():
    event = _cg.CGEventCreate(None)

    if not event:
        return 0, 0

    point = _cg.CGEventGetLocation(event)
    _cf.CFRelease(event)

    return int(round(point.x)), int(round(point.y))

"""Keybind definitions and X11 keycode resolution."""

__all__ = ["resolve_keycode"]


def resolve_keycode(key_name: str):
    """Convert a key name (e.g. 'Escape', 'F5') to an X11 keycode.
    Returns None if the key can't be resolved."""
    import ctypes
    try:
        xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
    except OSError:
        return None
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XStringToKeysym.argtypes = [ctypes.c_char_p]
    xlib.XStringToKeysym.restype = ctypes.c_ulong
    xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xlib.XKeysymToKeycode.restype = ctypes.c_uint

    display = xlib.XOpenDisplay(None)
    if not display:
        return None
    keysym = xlib.XStringToKeysym(key_name.encode())
    if keysym == 0:
        return None
    keycode = xlib.XKeysymToKeycode(display, keysym)
    return keycode if keycode else None

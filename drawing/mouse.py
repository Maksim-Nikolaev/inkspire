"""Platform-dispatched mouse control."""

import sys

if sys.platform == "win32":
    from drawing._mouse_win32 import mouse_move, mouse_down, mouse_up, get_mouse_pos
else:
    from drawing._mouse_x11 import mouse_move, mouse_down, mouse_up, get_mouse_pos

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

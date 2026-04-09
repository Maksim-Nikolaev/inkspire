"""Platform-dispatched keybind resolution and global key press detection."""

import sys

if sys.platform == "win32":
    from core._keybinds_win32 import resolve_keycode, is_key_pressed
else:
    from core._keybinds_x11 import resolve_keycode, is_key_pressed

__all__ = ["resolve_keycode", "is_key_pressed"]

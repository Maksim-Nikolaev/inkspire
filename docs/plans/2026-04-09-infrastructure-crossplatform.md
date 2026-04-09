# Infrastructure: Cross-Platform Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Abstract X11-specific mouse, keyboard, and clipboard code behind platform-dispatch modules so Inkspire runs on both Linux and Windows.

**Architecture:** Each platform-specific subsystem (mouse, keybinds, clipboard) gets a public API module that auto-detects the platform via `sys.platform` and delegates to a `_x11` or `_win32` private implementation. Consumers only import the public module. A `pyproject.toml` is added for packaging.

**Tech Stack:** ctypes (user32.dll on Windows, libX11/libXtst on Linux), PIL.ImageGrab, subprocess fallbacks for Linux clipboard.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `drawing/mouse.py` | Create | Public mouse API + platform dispatch |
| `drawing/_mouse_x11.py` | Rename from `mouse_x11.py` | X11 mouse control (remove key functions) |
| `drawing/_mouse_win32.py` | Create | Win32 mouse control via user32.dll |
| `core/keybinds.py` | Rewrite | Public keybind API + platform dispatch |
| `core/_keybinds_x11.py` | Create | X11 keycode resolution + key press detection |
| `core/_keybinds_win32.py` | Create | Win32 VK codes + GetAsyncKeyState |
| `core/clipboard.py` | Create | Platform-aware clipboard image extraction |
| `drawing/engine.py` | Modify | Update imports |
| `main.py` | Modify | Update imports, extract clipboard, add main() |
| `pyproject.toml` | Create | Package metadata and entry points |

---

### Task 1: Create X11 mouse backend (rename + trim)

**Files:**
- Rename: `drawing/mouse_x11.py` → `drawing/_mouse_x11.py`

- [ ] **Step 1: Rename the file and remove key-press functions**

Rename `drawing/mouse_x11.py` to `drawing/_mouse_x11.py` and remove `is_key_pressed`, `is_escape_pressed`, and the escape keycode setup. The file should contain only mouse functions:

```python
"""X11 mouse control via ctypes (libX11 + libXtst)."""

import ctypes
import sys

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

_xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
_xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")

_xlib.XOpenDisplay.restype = ctypes.c_void_p
_xlib.XDefaultRootWindow.restype = ctypes.c_ulong

_display = _xlib.XOpenDisplay(None)
if not _display:
    print("Error: cannot open X display. Are you running under X11?")
    sys.exit(1)
_root = _xlib.XDefaultRootWindow(_display)


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
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('drawing/_mouse_x11.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git rm drawing/mouse_x11.py
git add drawing/_mouse_x11.py
git commit -m "rename mouse_x11 to _mouse_x11 and remove key functions"
```

---

### Task 2: Create Win32 mouse backend

**Files:**
- Create: `drawing/_mouse_win32.py`

- [ ] **Step 1: Create the Win32 mouse module**

```python
"""Win32 mouse control via ctypes (user32.dll)."""

import ctypes
import ctypes.wintypes

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]

_user32 = ctypes.windll.user32

# SendInput structures
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
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('drawing/_mouse_win32.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add drawing/_mouse_win32.py
git commit -m "add Win32 mouse backend via user32.dll ctypes"
```

---

### Task 3: Create mouse dispatch module

**Files:**
- Create: `drawing/mouse.py`

- [ ] **Step 1: Create the platform dispatch module**

```python
"""Platform-dispatched mouse control."""

import sys

if sys.platform == "win32":
    from drawing._mouse_win32 import mouse_move, mouse_down, mouse_up, get_mouse_pos
else:
    from drawing._mouse_x11 import mouse_move, mouse_down, mouse_up, get_mouse_pos

__all__ = ["mouse_move", "mouse_down", "mouse_up", "get_mouse_pos"]
```

- [ ] **Step 2: Verify it imports on Linux**

Run: `python3 -c "from drawing.mouse import mouse_move, mouse_down, mouse_up, get_mouse_pos; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add drawing/mouse.py
git commit -m "add platform-dispatch mouse module"
```

---

### Task 4: Create X11 keybinds backend

**Files:**
- Create: `core/_keybinds_x11.py`

- [ ] **Step 1: Create the X11 keybinds module**

Combines keycode resolution from current `core/keybinds.py` and `is_key_pressed` from the old `mouse_x11.py`:

```python
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
```

- [ ] **Step 2: Verify syntax and import**

Run: `python3 -c "from core._keybinds_x11 import resolve_keycode, is_key_pressed; print(resolve_keycode('F5')); print('OK')"`
Expected: A keycode number, then `OK`

- [ ] **Step 3: Commit**

```bash
git add core/_keybinds_x11.py
git commit -m "extract X11 keybinds into dedicated backend module"
```

---

### Task 5: Create Win32 keybinds backend

**Files:**
- Create: `core/_keybinds_win32.py`

- [ ] **Step 1: Create the Win32 keybinds module**

```python
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

# Add letter keys a-z (VK codes 0x41-0x5A, key names match X11 convention)
for i in range(26):
    _VK_MAP[chr(ord("a") + i)] = 0x41 + i

# Add digit keys 0-9
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
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('core/_keybinds_win32.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/_keybinds_win32.py
git commit -m "add Win32 keybinds backend with VK codes and GetAsyncKeyState"
```

---

### Task 6: Rewrite keybinds dispatch module

**Files:**
- Modify: `core/keybinds.py`

- [ ] **Step 1: Rewrite as platform dispatch**

Replace the entire content of `core/keybinds.py`:

```python
"""Platform-dispatched keybind resolution and global key press detection."""

import sys

if sys.platform == "win32":
    from core._keybinds_win32 import resolve_keycode, is_key_pressed
else:
    from core._keybinds_x11 import resolve_keycode, is_key_pressed

__all__ = ["resolve_keycode", "is_key_pressed"]
```

- [ ] **Step 2: Verify it imports on Linux**

Run: `python3 -c "from core.keybinds import resolve_keycode, is_key_pressed; print(resolve_keycode('F5')); print('OK')"`
Expected: A keycode number, then `OK`

- [ ] **Step 3: Commit**

```bash
git add core/keybinds.py
git commit -m "rewrite keybinds as platform dispatch module"
```

---

### Task 7: Create clipboard module

**Files:**
- Create: `core/clipboard.py`

- [ ] **Step 1: Create the clipboard module**

Extract clipboard logic from `main.py`:

```python
"""Platform-aware clipboard image extraction."""

import subprocess
import io
from PIL import Image

__all__ = ["get_clipboard_image"]


def get_clipboard_image():
    """Get an image from the system clipboard.

    Returns a PIL Image or None if no image is available.
    """
    img = None

    # PIL ImageGrab works natively on Windows and on Linux with xclip/wl-paste
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
    except Exception:
        pass

    if img is not None:
        return img

    # Linux fallbacks via subprocess
    import sys
    if sys.platform == "win32":
        return None

    # xclip
    for mime in ["image/png", "image/bmp", "image/jpeg"]:
        try:
            data = subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-t", mime, "-o"],
                stderr=subprocess.DEVNULL)
            return Image.open(io.BytesIO(data))
        except Exception:
            continue

    # xsel
    try:
        data = subprocess.check_output(
            ["xsel", "--clipboard", "--output"],
            stderr=subprocess.DEVNULL)
        return Image.open(io.BytesIO(data))
    except Exception:
        pass

    # wl-paste (Wayland)
    try:
        data = subprocess.check_output(
            ["wl-paste", "--type", "image/png"],
            stderr=subprocess.DEVNULL)
        return Image.open(io.BytesIO(data))
    except Exception:
        pass

    return None
```

- [ ] **Step 2: Verify syntax and import**

Run: `python3 -c "from core.clipboard import get_clipboard_image; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/clipboard.py
git commit -m "extract clipboard image logic into cross-platform module"
```

---

### Task 8: Update drawing engine imports

**Files:**
- Modify: `drawing/engine.py:5`

- [ ] **Step 1: Update imports**

Change line 5 from:
```python
from drawing.mouse_x11 import mouse_move, mouse_down, mouse_up, get_mouse_pos, is_escape_pressed
```
to:
```python
from drawing.mouse import mouse_move, mouse_down, mouse_up, get_mouse_pos
```

Also update the `__init__` default cancel check. Change line 14 from:
```python
self._cancel_check = cancel_check or is_escape_pressed
```
to:
```python
if cancel_check is None:
    from core.keybinds import resolve_keycode, is_key_pressed
    esc_code = resolve_keycode("Escape")
    cancel_check = (lambda: is_key_pressed(esc_code)) if esc_code else (lambda: False)
self._cancel_check = cancel_check
```

- [ ] **Step 2: Verify syntax and import**

Run: `python3 -c "from drawing.engine import DrawEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add drawing/engine.py
git commit -m "update drawing engine to use platform-dispatch mouse and keybinds"
```

---

### Task 9: Update main.py imports and clipboard

**Files:**
- Modify: `main.py:1-38,622-675,776-778`

- [ ] **Step 1: Update module docstring**

Replace lines 2-12:
```python
"""
Inkspire – traces line art by moving the mouse along extracted contours.
Uses ctypes X11 calls for fast, jitter-free mouse control.

Supports: B/W line art, colored images, halftones via multiple detection modes.

Usage: python3 main.py

Requires: opencv-python, numpy, Pillow
Install:  sudo pip install opencv-python numpy Pillow --break-system-packages
System:   sudo apt install python3-tk python3-pil.imagetk
"""
```
with:
```python
"""
Inkspire – traces line art by moving the mouse along extracted contours.

Supports: B/W line art, colored images, halftones via multiple detection modes.
Platforms: Linux (X11) and Windows.

Usage: python3 main.py
"""
```

- [ ] **Step 2: Update imports**

Replace lines 37-38:
```python
from core.keybinds import resolve_keycode
from drawing.mouse_x11 import is_key_pressed
```
with:
```python
from core.keybinds import resolve_keycode, is_key_pressed
from core.clipboard import get_clipboard_image
```

- [ ] **Step 3: Replace clipboard method body**

Replace the `_paste_from_clipboard` method (the part that finds the image) with:

```python
    def _paste_from_clipboard(self):
        img = get_clipboard_image()

        if img is None:
            self._update_status("No image in clipboard.")
            return

        rgb = np.array(img.convert("RGB"))
        self.gray_image = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        self.image_path = "(clipboard)"
        self.lbl_file.config(text="(pasted from clipboard)")
        self._do_crop()
```

- [ ] **Step 4: Add main() entry point**

Replace the bottom of the file:
```python
if __name__ == "__main__":
    Inkspire()
```
with:
```python
def main():
    Inkspire()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Verify syntax and import**

Run: `python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "update main.py to use platform-dispatch imports and extract clipboard"
```

---

### Task 10: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "inkspire"
version = "0.3.0"
description = "Trace line art by moving the mouse along extracted contours"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "opencv-python>=4.8",
    "numpy>=1.24",
    "Pillow>=10.0",
    "fonttools>=4.40",
]

[project.scripts]
inkspire = "main:main"

[project.gui-scripts]
inkspire-gui = "main:main"
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "add pyproject.toml for packaging"
```

---

### Task 11: Smoke test full application

- [ ] **Step 1: Verify all imports resolve**

Run: `python3 -c "from drawing.mouse import mouse_move; from core.keybinds import resolve_keycode, is_key_pressed; from core.clipboard import get_clipboard_image; from drawing.engine import DrawEngine; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 2: Verify app launches**

Run: `timeout 3 python3 main.py 2>&1 || true`
Expected: Window opens briefly (timeout kills it). No import errors.

- [ ] **Step 3: Verify old mouse_x11.py is gone**

Run: `test -f drawing/mouse_x11.py && echo "FAIL: old file still exists" || echo "OK: old file removed"`
Expected: `OK: old file removed`

- [ ] **Step 4: Commit any fixups if needed**

# Infrastructure Pass: Cross-Platform Abstraction

**Goal:** Abstract platform-specific code (mouse control, global hotkeys, clipboard) behind clean interfaces so Inkspire runs on both Linux (X11) and Windows. Add pyproject.toml for packaging.

**Platforms:** Linux (X11) and Windows. macOS deferred.

---

## 1. Mouse Backend

### Public API: `drawing/mouse.py`

```python
mouse_move(x: int, y: int) -> None
mouse_down(button: str) -> None   # "left" or "right"
mouse_up(button: str) -> None
get_mouse_pos() -> tuple[int, int]
```

Platform dispatch at module level via `sys.platform`. Consumers import from `drawing.mouse` only.

### `drawing/_mouse_x11.py`

Current `drawing/mouse_x11.py` renamed. Contains libX11/libXtst ctypes calls: `XWarpPointer`, `XTestFakeButtonEvent`, `XQueryPointer`. The `is_key_pressed` and `is_escape_pressed` functions move to `core/keybinds`.

### `drawing/_mouse_win32.py`

ctypes calls to user32.dll:
- `SetCursorPos(x, y)` for mouse movement
- `SendInput` with `MOUSEINPUT` struct for button press/release (`MOUSEEVENTF_LEFTDOWN`, `MOUSEEVENTF_LEFTUP`, `MOUSEEVENTF_RIGHTDOWN`, `MOUSEEVENTF_RIGHTUP`)
- `GetCursorPos` for position query

---

## 2. Keybinds Backend

### Public API: `core/keybinds.py`

```python
resolve_keycode(key_name: str) -> int | None
is_key_pressed(keycode: int) -> bool
```

Platform dispatch at module level. `is_key_pressed` works globally (detects keys even when another app has focus).

### `core/_keybinds_x11.py`

Extracted from current `core/keybinds.py` and `drawing/mouse_x11.py`:
- `resolve_keycode`: `XStringToKeysym` → `XKeysymToKeycode`
- `is_key_pressed`: `XQueryKeymap` bit check

### `core/_keybinds_win32.py`

- `resolve_keycode`: Dictionary mapping key names ("F5", "Escape", "a"-"z", etc.) to Windows VK_ codes
- `is_key_pressed`: `GetAsyncKeyState(vk_code)` — returns True if high bit set

---

## 3. Clipboard

### `core/clipboard.py`

```python
get_clipboard_image() -> PIL.Image.Image | None
```

Extracts the inline clipboard logic currently in `main.py._paste_from_clipboard`.

- **Windows:** `PIL.ImageGrab.grabclipboard()` works natively on Windows — no extra dependencies needed.
- **Linux:** Try `PIL.ImageGrab.grabclipboard()` first, then fall back to subprocess calls: `xclip`, `xsel`, `wl-paste` (current behavior).

Returns `None` with no exceptions if clipboard is empty or has no image.

---

## 4. Packaging: `pyproject.toml`

```toml
[project]
name = "inkspire"
version = "0.3.0"
requires-python = ">=3.10"
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

Requires adding a `def main():` wrapper around the `Inkspire()` call in `main.py`.

---

## 5. main.py Cleanup

- `from drawing.mouse_x11 import ...` → `from drawing.mouse import ...`
- `from drawing.mouse_x11 import is_key_pressed` → `from core.keybinds import is_key_pressed`
- Inline clipboard code → `from core.clipboard import get_clipboard_image`
- Wrap `Inkspire()` in `def main():` for entry point
- Remove `_paste_from_clipboard` body, replace with call to `get_clipboard_image()`

---

## File Changes Summary

| File | Action |
|---|---|
| `drawing/mouse.py` | Create — public API with platform dispatch |
| `drawing/_mouse_x11.py` | Rename from `drawing/mouse_x11.py`, remove key functions |
| `drawing/_mouse_win32.py` | Create — Win32 ctypes mouse control |
| `core/keybinds.py` | Rewrite — public API with platform dispatch |
| `core/_keybinds_x11.py` | Create — extracted X11 keycode/keymap logic |
| `core/_keybinds_win32.py` | Create — VK codes + GetAsyncKeyState |
| `core/clipboard.py` | Create — extracted from main.py |
| `main.py` | Modify — new imports, extract clipboard, add main() |
| `drawing/engine.py` | Modify — update import path |
| `pyproject.toml` | Create |
| `requirements.txt` | Keep for backward compat, but pyproject.toml is canonical |

## Out of Scope

- macOS support (Quartz/pyobjc) — deferred
- Test scaffolding — deferred to v0.4.0
- core/constants — not needed yet

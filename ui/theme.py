"""Palette, fonts and CustomTkinter setup shared by every window."""

import atexit
import ctypes
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from core.config import CONFIG_DIR
from core.proc import system_env

__all__ = [
    "ctk", "setup", "is_dark", "pick", "font", "mono_font", "apply_window_icon",
    "icon_path", "watch_appearance", "BG", "SURFACE", "SURFACE_2", "SURFACE_3",
    "BORDER", "BORDER_STRONG", "TEXT", "TEXT_2", "MUTED", "ACCENT", "ACCENT_HOVER",
    "ACCENT_SOFT", "ACCENT_TEXT", "ON_ACCENT", "DANGER", "DANGER_SOFT", "WARN",
    "WARN_SOFT", "OK", "OK_SOFT", "RADIUS", "CARD_RADIUS",
]

BG = ("#f5f6f8", "#0c0f15")
SURFACE = ("#ffffff", "#141821")
SURFACE_2 = ("#f0f2f5", "#1b202b")
SURFACE_3 = ("#e8ebf0", "#232937")
BORDER = ("#e2e5ea", "#262c39")
BORDER_STRONG = ("#cdd2da", "#353d4e")
TEXT = ("#111827", "#e8ebf1")
TEXT_2 = ("#374151", "#c3c9d5")
MUTED = ("#6b7280", "#8b94a7")
ACCENT = ("#4f46e5", "#8b93ff")
ACCENT_HOVER = ("#4338ca", "#a5abff")
ACCENT_SOFT = ("#eef0ff", "#1f2147")
ACCENT_TEXT = ("#3730a3", "#c7cbff")
ON_ACCENT = ("#ffffff", "#0c0f15")
DANGER = ("#dc2626", "#f87171")
DANGER_SOFT = ("#fef2f2", "#2a1416")
WARN = ("#b45309", "#fbbf24")
WARN_SOFT = ("#fff8eb", "#261d0c")
OK = ("#047857", "#34d399")
OK_SOFT = ("#ecfdf5", "#0f2a21")

RADIUS = 8
CARD_RADIUS = 12

_UI_FAMILIES = ["Inter", "Noto Sans", "Cantarell", "Ubuntu"]
_MONO_FAMILIES = ["JetBrains Mono", "SF Mono", "Menlo", "Cascadia Mono", "Consolas", "Noto Sans Mono", "DejaVu Sans Mono"]
_PORTAL_SCHEME = re.compile(r"'org\.freedesktop\.appearance', 'color-scheme', <(?:<)?uint32 (\d)>")

_family = "TkDefaultFont"
_mono_family = "TkFixedFont"


def _import_customtkinter():
    if not sys.platform.startswith("linux"):
        import customtkinter

        return customtkinter

    # CustomTkinter copies its fonts into ~/.fonts on import; keep that copy in our own folder.
    private_home = CONFIG_DIR / "ctk"
    private_home.mkdir(parents=True, exist_ok=True)
    real_home = os.environ.get("HOME")
    os.environ["HOME"] = str(private_home)

    try:
        import customtkinter
    finally:
        if real_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = real_home

    _register_font_dir(private_home / ".fonts")

    return customtkinter


def _register_font_dir(folder: Path):
    try:
        fontconfig = ctypes.cdll.LoadLibrary("libfontconfig.so.1")
    except OSError:
        return

    fontconfig.FcConfigAppFontAddDir.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    fontconfig.FcConfigAppFontAddDir.restype = ctypes.c_int
    fontconfig.FcConfigAppFontAddDir(None, str(folder).encode())


ctk = _import_customtkinter()


def icon_path(name) -> Path:
    return Path(__file__).resolve().parent / "icons" / name


def _linux_prefers_dark() -> bool:
    try:
        out = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
             "--object-path", "/org/freedesktop/portal/desktop",
             "--method", "org.freedesktop.portal.Settings.ReadOne",
             "org.freedesktop.appearance", "color-scheme"],
            capture_output=True, text=True, timeout=2, env=system_env(),
        ).stdout
        match = re.search(r"uint32 (\d)", out)

        if match and match.group(1) in ("1", "2"):
            return match.group(1) == "1"
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2, env=system_env(),
        ).stdout

        if "dark" in out:
            return True

        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=2, env=system_env(),
        ).stdout

        return "-dark" in out.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _initial_mode() -> str:
    forced = os.environ.get("INKSPIRE_THEME", "").lower()

    if forced in ("light", "dark"):
        return forced

    # CustomTkinter's "system" mode runs gsettings every 30 ms on Linux, so Linux gets a fixed mode plus watch_appearance().
    if sys.platform.startswith("linux"):
        return "dark" if _linux_prefers_dark() else "light"

    return "system"


def watch_appearance(root: tk.Misc):
    """Follow the desktop portal's colour-scheme changes on Linux."""
    if not sys.platform.startswith("linux") or os.environ.get("INKSPIRE_THEME"):
        return

    def listen():
        try:
            proc = subprocess.Popen(
                ["gdbus", "monitor", "--session", "--dest", "org.freedesktop.portal.Desktop",
                 "--object-path", "/org/freedesktop/portal/desktop"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=system_env(),
            )
        except OSError:
            return

        atexit.register(proc.terminate)

        for line in proc.stdout:
            match = _PORTAL_SCHEME.search(line)

            if match:
                mode = "dark" if match.group(1) == "1" else "light"

                try:
                    root.after(0, lambda m=mode: ctk.set_appearance_mode(m))
                except (RuntimeError, tk.TclError):
                    break

        proc.terminate()

    threading.Thread(target=listen, daemon=True).start()


def _first_family(candidates, fallback_named_font) -> str:
    available = set(tkfont.families())

    for family in candidates:
        if family in available:
            return family

    return tkfont.nametofont(fallback_named_font).actual()["family"]


def _ui_family() -> str:
    if sys.platform.startswith("linux"):
        return _first_family(_UI_FAMILIES, "TkDefaultFont")

    return tkfont.nametofont("TkDefaultFont").actual()["family"]


def _theme(family: str) -> dict:
    return {
        "CTk": {"fg_color": list(BG)},
        "CTkToplevel": {"fg_color": list(BG)},
        "CTkFrame": {
            "corner_radius": CARD_RADIUS,
            "border_width": 0,
            "fg_color": list(SURFACE),
            "top_fg_color": list(SURFACE_2),
            "border_color": list(BORDER),
        },
        "CTkButton": {
            "corner_radius": RADIUS,
            "border_width": 0,
            "fg_color": list(ACCENT),
            "hover_color": list(ACCENT_HOVER),
            "border_color": list(BORDER_STRONG),
            "text_color": list(ON_ACCENT),
            "text_color_disabled": list(MUTED),
        },
        "CTkLabel": {
            "corner_radius": 0,
            "border_width": 0,
            "fg_color": "transparent",
            "border_color": list(BORDER),
            "text_color": list(TEXT),
        },
        "CTkEntry": {
            "corner_radius": RADIUS,
            "border_width": 1,
            "fg_color": list(SURFACE),
            "border_color": list(BORDER_STRONG),
            "text_color": list(TEXT),
            "placeholder_text_color": list(MUTED),
        },
        "CTkCheckBox": {
            "corner_radius": 5,
            "border_width": 2,
            "fg_color": list(ACCENT),
            "border_color": list(BORDER_STRONG),
            "hover_color": list(ACCENT_HOVER),
            "checkmark_color": list(ON_ACCENT),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkSwitch": {
            "corner_radius": 1000,
            "border_width": 3,
            "button_length": 0,
            "fg_color": list(BORDER_STRONG),
            "progress_color": list(ACCENT),
            "button_color": ("#ffffff", "#ffffff"),
            "button_hover_color": ("#ffffff", "#ffffff"),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkRadioButton": {
            "corner_radius": 1000,
            "border_width_checked": 5,
            "border_width_unchecked": 2,
            "fg_color": list(ACCENT),
            "border_color": list(BORDER_STRONG),
            "hover_color": list(ACCENT_HOVER),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkProgressBar": {
            "corner_radius": 1000,
            "border_width": 0,
            "fg_color": list(SURFACE_3),
            "progress_color": list(ACCENT),
            "border_color": list(BORDER),
        },
        "CTkSlider": {
            "corner_radius": 1000,
            "button_corner_radius": 1000,
            "border_width": 6,
            "button_length": 0,
            "fg_color": list(SURFACE_3),
            "progress_color": list(ACCENT),
            "button_color": list(ACCENT),
            "button_hover_color": list(ACCENT_HOVER),
        },
        "CTkOptionMenu": {
            "corner_radius": RADIUS,
            "fg_color": list(SURFACE_2),
            "button_color": list(SURFACE_3),
            "button_hover_color": list(BORDER_STRONG),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkComboBox": {
            "corner_radius": RADIUS,
            "border_width": 1,
            "fg_color": list(SURFACE),
            "border_color": list(BORDER_STRONG),
            "button_color": list(BORDER_STRONG),
            "button_hover_color": list(MUTED),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkScrollbar": {
            "corner_radius": 1000,
            "border_spacing": 3,
            "fg_color": "transparent",
            "button_color": list(BORDER_STRONG),
            "button_hover_color": list(MUTED),
        },
        "CTkSegmentedButton": {
            "corner_radius": RADIUS,
            "border_width": 2,
            "fg_color": list(SURFACE_3),
            "selected_color": list(SURFACE),
            "selected_hover_color": list(SURFACE),
            "unselected_color": list(SURFACE_3),
            "unselected_hover_color": list(BORDER),
            "text_color": list(TEXT),
            "text_color_disabled": list(MUTED),
        },
        "CTkTextbox": {
            "corner_radius": RADIUS,
            "border_width": 1,
            "fg_color": list(SURFACE),
            "border_color": list(BORDER_STRONG),
            "text_color": list(TEXT),
            "scrollbar_button_color": list(BORDER_STRONG),
            "scrollbar_button_hover_color": list(MUTED),
        },
        "CTkScrollableFrame": {"label_fg_color": list(SURFACE_2)},
        "DropdownMenu": {
            "fg_color": list(SURFACE),
            "hover_color": list(SURFACE_3),
            "text_color": list(TEXT),
        },
        "CTkFont": {"family": family, "size": 13, "weight": "normal"},
    }


def setup(root: tk.Misc):
    """Apply the Inkspire theme. Call once, right after creating the root window."""
    global _family, _mono_family

    _family = _ui_family()
    _mono_family = _first_family(_MONO_FAMILIES, "TkFixedFont")
    ctk.ThemeManager.theme = _theme(_family)

    if sys.platform.startswith("linux"):
        scaling = root.winfo_fpixels("1i") / 96

        if scaling > 1.1:
            ctk.set_widget_scaling(scaling)
            ctk.set_window_scaling(scaling)

    root.option_add("*Font", (_family, 10))


ctk.set_appearance_mode(_initial_mode())
ctk.ThemeManager.theme = _theme("TkDefaultFont")


def is_dark() -> bool:
    return ctk.get_appearance_mode() == "Dark"


def pick(color) -> str:
    """Resolve a (light, dark) colour pair for plain Tk widgets."""
    if isinstance(color, (tuple, list)):
        return color[1] if is_dark() else color[0]

    return color


def font(size=13, weight="normal") -> "ctk.CTkFont":
    return ctk.CTkFont(family=_family, size=size, weight=weight)


def mono_font(size=12, weight="normal") -> "ctk.CTkFont":
    return ctk.CTkFont(family=_mono_family, size=size, weight=weight)


def apply_window_icon(window: tk.Misc):
    """Set the app icon; on Windows this also stops CustomTkinter swapping in its own."""
    try:
        if sys.platform == "win32":
            window.iconbitmap(str(icon_path("inkspire.ico")))
        else:
            icon = tk.PhotoImage(master=window, file=str(icon_path("inkspire-256.png")))
            window.iconphoto(False, icon)
            window._inkspire_icon = icon
    except tk.TclError:
        pass

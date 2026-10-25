#!/usr/bin/env python3
"""
Inkspire – traces line art by moving the mouse along extracted contours.

Supports: B/W line art, colored images, halftones via multiple detection modes.
Platforms: Linux (X11, Wayland via Xwayland), Windows and macOS.

Usage: python3 main.py [--self-test]
"""

import sys

# Fix blurry UI and wrong coordinates on Windows with display scaling
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import math
import os
import threading
import tkinter as tk

import cv2
import numpy as np
from PIL import Image

from core.proc import restore_system_env

restore_system_env()

from ui import theme
from ui.theme import ctk
from core import accessibility
from core.clipboard import get_clipboard_image
from core.config import load_config, save_config, load_session, save_session
from core.fonts import discover_fonts, regular_path
from core.keybinds import resolve_keycode, is_key_pressed
from core.optimize import optimize_path
from detection.contours import extract_contours
from detection.modes import detect_art_bounds
from detection.suggest import compute_suggested
from detection.svg import load_svg
from detection.text import render_text
from drawing.engine import DrawEngine
from ui.about_dialog import AboutDialog
from ui.accessibility_dialog import AccessibilityDialog
from ui.canvas_picker import CanvasPicker
from ui.crop_dialog import CropDialog
from ui.file_dialog import ask_open_filename
from ui.keybinds_dialog import KeybindsDialog
from ui.preview import PreviewCanvas, PreviewWindow, render_preview
from ui.tooltip import Tooltip
from ui.widgets import (
    AutoScrollFrame, Card, FontList, Pill, Segmented, SliderRow, Toggle, ToggleRow, button, kbd, key_label,
)

MODES = [
    ("Threshold", "Threshold"), ("Canny Edge", "Canny"),
    ("Adaptive Threshold", "Adaptive"), ("Auto", "Auto"),
]
IMAGE_TYPES = [
    ("All supported", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp *.svg"),
    ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
    ("SVG", "*.svg"),
    ("All files", "*.*"),
]
PREFERRED_FONTS = ["Noto Sans", "DejaVu Sans", "Segoe UI", "Arial", "Helvetica Neue", "Helvetica"]
SIDEBAR_WIDTH = 384


class Inkspire:
    def __init__(self, self_test=False):
        self.root = ctk.CTk()
        theme.setup(self.root)
        theme.apply_window_icon(self.root)
        self.root.title("Inkspire")

        # CTk multiplies geometry by the window scaling, so the screen size is converted to unscaled units first.
        scaling = ctk.ScalingTracker.get_window_scaling(self.root)
        width = min(1160, round(self.root.winfo_screenwidth() / scaling) - 80)
        height = min(800, round(self.root.winfo_screenheight() / scaling) - 110)

        self.root.geometry(f"{width}x{height}")
        self.root.minsize(900, 600)

        self.image_path = None
        self.gray_image = None
        self.cropped_image = None
        self._image_contours = []
        self._image_bounds = None
        self._textsvg_contours = []
        self._textsvg_bounds = None
        self._svg_name = None
        self._preview_timer = None
        self._preview_extract = False
        self._text_timer = None
        self._progress = (0, 0)
        self._progress_shown = None
        self._engine_state = None
        self._polling_paused = False
        self._accessibility_dialog = None
        self.config = load_config()

        self._start_key_name = self.config.get("start_key", "F5")
        self._stop_key_name = self.config.get("stop_key", "Escape")
        stop_keycode = resolve_keycode(self._stop_key_name)
        cancel_check = (lambda: is_key_pressed(stop_keycode)) if stop_keycode is not None else None
        self.draw_engine = DrawEngine(on_status=self._update_status, cancel_check=cancel_check, on_progress=self._on_progress)

        self._widgets: dict[str, SliderRow] = {}

        self.detect_mode = tk.StringVar(value="Auto")
        self.input_mode_var = tk.StringVar(value="image")

        cfg = self.config
        self.scale = tk.DoubleVar(value=cfg.get("scale", 1.0))
        self.offset_x = tk.StringVar(value=str(cfg.get("offset_x", 200)))
        self.offset_y = tk.StringVar(value=str(cfg.get("offset_y", 200)))
        self.speed = tk.IntVar(value=cfg.get("speed", 50))
        self.threshold = tk.IntVar(value=128)
        self.canny_lo = tk.IntVar(value=50)
        self.canny_hi = tk.IntVar(value=150)
        self.adaptive_block = tk.IntVar(value=11)
        self.adaptive_c = tk.IntVar(value=2)
        self.blur_radius = tk.IntVar(value=0)
        self.morph_iter = tk.IntVar(value=0)
        self.min_contour_len = tk.IntVar(value=10)
        self.simplify = tk.DoubleVar(value=1.0)
        self.mouse_button = tk.StringVar(value=cfg.get("mouse_button", "right"))
        self.delay_before = tk.IntVar(value=cfg.get("delay_before", 3))
        self.use_skeleton = tk.BooleanVar(value=False)
        self.relative_offset = tk.BooleanVar(value=cfg.get("relative_offset", True))
        self.auto_preview = tk.BooleanVar(value=cfg.get("auto_preview", True))
        self.optimize_path = tk.BooleanVar(value=cfg.get("optimize_path", False))

        self.font_size = tk.IntVar(value=48)
        self.font_path = None
        self._font_list = []
        self._fonts_loading = False

        self.preview = None
        self._restoring_session = False

        self._build_gui()
        self._bind_keys()
        self._setup_traces()
        self._update_mode_visibility()
        self._update_position_visibility()

        if not self_test:
            self._restore_session()

        self._show_page()
        self._refresh_stats()

        ctk.AppearanceModeTracker.add(self._on_appearance_change, self.root)
        theme.watch_appearance(self.root)

        self._start_keycode = resolve_keycode(self._start_key_name)
        self._start_key_was_pressed = False
        self._poll()

        if self_test:
            self.root.after(1200, self._self_test)
        elif accessibility.needs_permission():
            self.root.after(600, self._check_accessibility)

        self.root.mainloop()

    @property
    def input_mode(self):
        return self.input_mode_var.get()

    @property
    def contours(self):
        return self._image_contours if self.input_mode == "image" else self._textsvg_contours

    @contours.setter
    def contours(self, value):
        if self.input_mode == "image":
            self._image_contours = value
        else:
            self._textsvg_contours = value

    @property
    def contour_bounds(self):
        return self._image_bounds if self.input_mode == "image" else self._textsvg_bounds

    @contour_bounds.setter
    def contour_bounds(self, value):
        if self.input_mode == "image":
            self._image_bounds = value
        else:
            self._textsvg_bounds = value

    def _current_shape(self):
        if self.input_mode == "image" and self.cropped_image is not None:
            return self.cropped_image.shape[:2]

        if self.contour_bounds:
            # A flat shape (a single straight line) still has to count as one pixel thick.
            return max(1, int(self.contour_bounds[1])), max(1, int(self.contour_bounds[0]))

        if self.contours:
            maxs = np.vstack(self.contours).max(axis=0)

            return int(maxs[1]) + 1, int(maxs[0]) + 1

        return None

    def _sync_all_widgets(self):
        for w in self._widgets.values():
            w.sync()

    def _set_widget_visible(self, var_name, visible):
        self._widgets[var_name].set_visible(visible)

    def _update_mode_visibility(self):
        mode = self.detect_mode.get()

        self._set_widget_visible("threshold", mode in ("Threshold", "Auto"))
        self._set_widget_visible("canny_lo", mode in ("Canny Edge", "Auto"))
        self._set_widget_visible("canny_hi", mode in ("Canny Edge", "Auto"))
        self._set_widget_visible("adaptive_block", mode in ("Adaptive Threshold", "Auto"))
        self._set_widget_visible("adaptive_c", mode in ("Adaptive Threshold", "Auto"))

    def _update_position_visibility(self):
        if self.relative_offset.get():
            self._fixed_row.grid_remove()
            self._position_hint.configure(text="The pointer position at start becomes the bottom-left corner.")
        else:
            self._fixed_row.grid()
            self._position_hint.configure(text="Screen pixels of the top-left corner.")

    def _set_mode(self, mode):
        if self.input_mode != mode:
            self.input_mode_var.set(mode)
            self._show_page()

    def _show_page(self):
        if self.input_mode == "image":
            self._page_text.pack_forget()
            self._page_image.pack(fill="x", before=self._card_draw)
            self._preview_view.set_empty(
                "Nothing to trace yet",
                "Open an image or paste one with Ctrl+V. Line art, photos and halftones all work.",
                [self._empty_open, self._empty_paste],
            )
        else:
            self._page_image.pack_forget()
            self._page_text.pack(fill="x", before=self._card_draw)
            self._preview_view.set_empty(
                "Nothing to trace yet",
                "Type some text and pick a font, or open an SVG file.",
                [self._empty_svg],
            )

            if not self._font_list and not self._fonts_loading:
                self.root.after(50, self._populate_fonts)
            elif not self._textsvg_contours:
                self._schedule_text_change()

        self._refresh_preview(extract=False)

    def _restore_session(self):
        session = load_session()

        if session is None:
            return

        det = session.get("detection_settings", {})

        if "mode" in det:
            self.detect_mode.set(det["mode"])

        for key, var in [
            ("threshold", self.threshold), ("canny_lo", self.canny_lo),
            ("canny_hi", self.canny_hi), ("adaptive_block", self.adaptive_block),
            ("adaptive_c", self.adaptive_c), ("blur_radius", self.blur_radius),
            ("morph_iter", self.morph_iter), ("min_contour_len", self.min_contour_len),
            ("simplify", self.simplify),
        ]:
            if key in det:
                var.set(det[key])

        if "skeleton" in det:
            self.use_skeleton.set(det["skeleton"])

        drw = session.get("drawing_settings", {})

        for key, var in [
            ("scale", self.scale), ("speed", self.speed), ("delay_before", self.delay_before),
        ]:
            if key in drw:
                var.set(drw[key])

        for key, var in [("offset_x", self.offset_x), ("offset_y", self.offset_y)]:
            if key in drw:
                var.set(str(drw[key]))

        for key, var in [
            ("mouse_button", self.mouse_button), ("relative_offset", self.relative_offset),
            ("auto_preview", self.auto_preview),
        ]:
            if key in drw:
                var.set(drw[key])

        if "optimize_path" in drw:
            self.optimize_path.set(drw["optimize_path"])

        self.root.after(10, self._sync_all_widgets)
        self.root.after(10, self._update_mode_visibility)

        if session.get("input_tab", 0) == 1:
            self.input_mode_var.set("textsvg")

        text = session.get("text_content", "")

        if text:
            self._text_box.delete("1.0", "end")
            self._text_box.insert("1.0", text)

        font_path = session.get("font_path")

        if font_path and os.path.exists(font_path):
            self.font_path = font_path
            self._lbl_font.configure(text=os.path.basename(font_path))

        font_size = session.get("font_size")

        if font_size:
            self.font_size.set(font_size)

        source = session.get("source_path")

        if source and source != "(clipboard)":
            if os.path.exists(source):
                self._restoring_session = True
                mode = self.input_mode

                def _restore_source():
                    try:
                        if source.lower().endswith(".svg"):
                            self._load_svg(source)
                        else:
                            self._load_image(source)
                    finally:
                        self._restoring_session = False
                        self._set_mode(mode)

                self.root.after(100, _restore_source)
            else:
                self.image_path = None

    def _setup_traces(self):
        live_vars = [
            self.threshold, self.min_contour_len, self.simplify,
            self.canny_lo, self.canny_hi, self.adaptive_block, self.adaptive_c,
            self.blur_radius, self.morph_iter,
        ]

        for var in live_vars:
            var.trace_add("write", lambda *_: self._schedule_preview_update())

        self.use_skeleton.trace_add("write", lambda *_: self._schedule_preview_update())
        self.detect_mode.trace_add("write", lambda *_: self._on_mode_change())
        self.scale.trace_add("write", lambda *_: self._schedule_preview_update(extract=False))
        self.font_size.trace_add("write", lambda *_: self._schedule_text_change())
        self.relative_offset.trace_add("write", lambda *_: self._update_position_visibility())
        self.auto_preview.trace_add("write", lambda *_: self._schedule_preview_update())

    def _on_mode_change(self):
        self._update_mode_visibility()
        self._schedule_preview_update()

    def _schedule_preview_update(self, extract=True):
        if extract and not self.auto_preview.get():
            return

        if self._preview_timer is not None:
            self.root.after_cancel(self._preview_timer)
            extract = extract or self._preview_extract

        self._preview_extract = extract
        self._preview_timer = self.root.after(250, lambda: self._refresh_preview(extract))

    def _refresh_preview(self, extract=True):
        self._preview_timer = None

        if extract and self.input_mode == "image":
            self._extract_contours()

        shape = self._current_shape()

        if self.contours and shape:
            self._preview_view.show(self.contours, self.scale.get(), shape)

            if self.preview and self.preview.is_open():
                self.preview.render(self.contours, self.scale.get(), shape)
        else:
            self._preview_view.clear()

        self._refresh_stats()

    def _refresh_stats(self):
        contours = self.contours
        shape = self._current_shape()

        if not contours or not shape:
            for pill in (self._pill_contours, self._pill_points, self._pill_size):
                pill.grid_remove()

            return

        total_points = sum(len(c) for c in contours)
        scale = self.scale.get()

        self._pill_contours.set(f"{len(contours)} contours")
        self._pill_points.set(f"{total_points:,} points".replace(",", " "))
        self._pill_size.set(f"{round(shape[1] * scale)} × {round(shape[0] * scale)} px", "accent")

        for pill in (self._pill_contours, self._pill_points, self._pill_size):
            pill.grid()

    def _build_gui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

        self._build_header()
        ctk.CTkFrame(self.root, height=1, corner_radius=0, fg_color=theme.BORDER).grid(row=1, column=0, columnspan=2, sticky="ew")
        self._build_sidebar()
        self._build_preview()

    def _build_header(self):
        header = ctk.CTkFrame(self.root, height=56, corner_radius=0, fg_color=theme.SURFACE)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        header.rowconfigure(0, weight=1)
        header.columnconfigure(2, weight=1)

        icon = Image.open(theme.icon_path("inkspire-256.png"))
        brand = ctk.CTkLabel(
            header, text="  Inkspire", image=ctk.CTkImage(icon, size=(28, 28)), compound="left",
            font=theme.font(16, "bold"),
        )
        brand.grid(row=0, column=0, padx=(18, 24))

        Segmented(
            header, [("image", "Image"), ("textsvg", "Text / SVG")], self.input_mode_var,
            command=lambda _: self._show_page(), width=220,
        ).grid(row=0, column=1)

        self._state_pill = Pill(header, "Ready")
        self._state_pill.grid(row=0, column=3, padx=(0, 10))

        self._access_button = button(
            header, "Mouse access off", self._show_accessibility, kind="ghost", height=28,
            fg_color=theme.WARN_SOFT, hover_color=theme.WARN_SOFT, text_color=theme.WARN,
        )
        self._access_button.grid(row=0, column=4, padx=(0, 6))
        self._access_button.grid_remove()

        button(header, "Keybinds", self._show_keybinds, kind="ghost", width=88).grid(row=0, column=5, padx=2)
        button(header, "About", self._show_about, kind="ghost", width=70).grid(row=0, column=6, padx=(2, 14))

    def _build_sidebar(self):
        side = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0, width=SIDEBAR_WIDTH)
        side.grid(row=2, column=0, sticky="ns")
        side.rowconfigure(0, weight=1)
        side.columnconfigure(0, weight=1)

        self._scroll = AutoScrollFrame(side, width=SIDEBAR_WIDTH, fg_color="transparent", corner_radius=0)
        self._scroll.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))

        self._page_image = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        self._page_text = ctk.CTkFrame(self._scroll, fg_color="transparent", corner_radius=0)
        self._build_image_page(self._page_image)
        self._build_text_page(self._page_text)

        self._card_draw = Card(self._scroll, "Drawing")
        self._card_draw.pack(fill="x", pady=(0, 10), padx=(0, 6))
        self._build_drawing_card(self._card_draw.body)

        self._build_actions(side)

    def _build_image_page(self, page):
        source = Card(page, "Source")
        source.pack(fill="x", pady=(0, 10), padx=(0, 6))
        body = source.body
        body.columnconfigure((0, 1, 2), weight=1, uniform="src")

        self.lbl_file = ctk.CTkLabel(body, text="No image loaded", font=theme.font(14, "bold"), anchor="w")
        self.lbl_file.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.lbl_crop = ctk.CTkLabel(body, text="PNG, JPG, BMP, GIF, TIFF, WebP or SVG", text_color=theme.MUTED, anchor="w", font=theme.font(12))
        self.lbl_crop.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        button(body, "Open…", self._browse, kind="primary").grid(row=2, column=0, sticky="ew", padx=(0, 4))
        button(body, "Paste", self._paste_from_clipboard).grid(row=2, column=1, sticky="ew", padx=4)
        self._btn_recrop = button(body, "Re-crop", self._recrop)
        self._btn_recrop.grid(row=2, column=2, sticky="ew", padx=(4, 0))

        detection = Card(page, "Detection")
        detection.pack(fill="x", pady=(0, 10), padx=(0, 6))
        body = detection.body
        Segmented(body, MODES, self.detect_mode).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        self._widgets["threshold"] = SliderRow(
            body, 1, "Threshold", self.threshold, is_int=True, from_=1, to=254, step=1,
            tooltip="Brightness cutoff (0 = black, 255 = white). Pixels darker than this become edges. Lower = more detected. Otsu auto-picks the optimal split.")
        self._widgets["canny_lo"] = SliderRow(
            body, 2, "Canny low", self.canny_lo, is_int=True, from_=1, to=300, step=1,
            tooltip="Minimum gradient strength to start an edge. Lower = more edges, more noise. Typical: 30-100.")
        self._widgets["canny_hi"] = SliderRow(
            body, 3, "Canny high", self.canny_hi, is_int=True, from_=1, to=500, step=1,
            tooltip="Minimum gradient strength to confirm an edge. Lower = more connected edges. Typical: 100-250. Keep above Canny low.")
        self._widgets["adaptive_block"] = SliderRow(
            body, 4, "Block size", self.adaptive_block, is_int=True, from_=3, to=99, step=2,
            tooltip="Size of the local neighborhood for adaptive threshold. Must be odd. Larger = smoother, less sensitive to small features. Typical: 7-21.")
        self._widgets["adaptive_c"] = SliderRow(
            body, 5, "Adaptive C", self.adaptive_c, is_int=True, from_=-20, to=20, step=1,
            tooltip="Constant subtracted from the local mean. Higher = fewer edges detected. Typical: 0-10.")

        processing = Card(page, "Processing")
        processing.pack(fill="x", pady=(0, 10), padx=(0, 6))
        self._widgets["blur_radius"] = SliderRow(
            processing.body, 0, "Blur", self.blur_radius, is_int=True, from_=0, to=20, step=1,
            tooltip="Gaussian blur radius applied before detection. Removes halftone dots and noise. 0 = off. For halftones try 2-5.")
        self._widgets["morph_iter"] = SliderRow(
            processing.body, 1, "Cleanup", self.morph_iter, is_int=True, from_=0, to=10, step=1,
            tooltip="Morphological passes on the edge mask. Close fills small gaps, open removes specks. 0 = off, 1-2 = light cleanup.")

        contours = Card(page, "Contours")
        contours.pack(fill="x", pady=(0, 10), padx=(0, 6))
        body = contours.body
        self._widgets["min_contour_len"] = SliderRow(
            body, 0, "Min length", self.min_contour_len, is_int=True, from_=1, to=500, step=1,
            tooltip="Contours shorter than this (in points) are discarded. Filters out noise fragments. Higher = cleaner but may lose small details.")
        self._widgets["simplify"] = SliderRow(
            body, 1, "Simplify", self.simplify, is_int=False, from_=0.1, to=10.0, step=0.1,
            tooltip="How aggressively paths are simplified. Higher = fewer points and faster drawing, but corners get rounded. 0.5 = detailed, 2.0 = aggressive.")

        ToggleRow(body, "Skeletonize to 1 px lines", self.use_skeleton,
                  tooltip="Thin all detected regions to 1 px centerlines. Useful when the source has thick brush strokes.").grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        ToggleRow(body, "Optimize path order", self.optimize_path,
                  tooltip="Reorder contours with nearest-neighbor search to minimize pen-up travel. Helps with scattered contours.").grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=4)

        self.btn_suggested = button(body, "Reset to suggested", self._apply_suggested, kind="ghost", state="disabled", height=28, text_color=theme.ACCENT)
        self.btn_suggested.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _build_text_page(self, page):
        svg = Card(page, "SVG")
        svg.pack(fill="x", pady=(0, 10), padx=(0, 6))
        body = svg.body
        body.columnconfigure(0, weight=1)
        self._lbl_svg = ctk.CTkLabel(body, text="No SVG loaded", anchor="w", text_color=theme.MUTED)
        self._lbl_svg.grid(row=0, column=0, sticky="ew")
        button(body, "Open SVG…", self._browse_svg).grid(row=0, column=1, sticky="e")

        text = Card(page, "Text")
        text.pack(fill="x", pady=(0, 10), padx=(0, 6))
        body = text.body
        body.columnconfigure(0, weight=1)

        self._text_box = ctk.CTkTextbox(body, height=84, wrap="word", font=theme.font(14))
        self._text_box.grid(row=0, column=0, columnspan=3, sticky="ew")
        self._text_box.bind("<KeyRelease>", lambda e: self._schedule_text_change())
        self._text_box.bind("<Control-o>", self._on_text_ctrl_o)

        font_head = ctk.CTkFrame(body, fg_color="transparent")
        font_head.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 6))
        font_head.columnconfigure(1, weight=1)
        ctk.CTkLabel(font_head, text="Font", text_color=theme.TEXT_2).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self._lbl_font = ctk.CTkLabel(font_head, text="Loading fonts…", text_color=theme.MUTED, anchor="e", font=theme.font(12))
        self._lbl_font.grid(row=0, column=1, sticky="e")

        self._font_picker = FontList(body, on_select=self._on_font_change, rows=6)
        self._font_picker.grid(row=2, column=0, columnspan=3, sticky="ew")

        font_buttons = ctk.CTkFrame(body, fg_color="transparent")
        font_buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 10))
        font_buttons.columnconfigure((0, 1), weight=1, uniform="font")
        button(font_buttons, "Font file…", self._browse_font, height=28).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        button(font_buttons, "Rescan fonts", lambda: self._populate_fonts(refresh=True), height=28).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        size_rows = ctk.CTkFrame(body, fg_color="transparent")
        size_rows.grid(row=4, column=0, columnspan=3, sticky="ew")
        size_rows.columnconfigure(1, weight=1)
        self._widgets["font_size"] = SliderRow(
            size_rows, 0, "Size (px)", self.font_size, is_int=True, from_=8, to=200, step=1,
            tooltip="Glyph height in pixels before drawing scale is applied.")

    def _build_drawing_card(self, body):
        self._widgets["scale"] = SliderRow(
            body, 0, "Scale", self.scale, is_int=False, from_=0.1, to=10.0, step=0.01,
            tooltip="Multiply the image dimensions by this factor for drawing. 1.0 = original size, 2.0 = double size.")
        self._widgets["speed"] = SliderRow(
            body, 1, "Speed", self.speed, is_int=True, from_=0, to=200, step=1,
            tooltip="Drawing speed in points per second. Higher = faster. 0 = as fast as possible.")
        self._widgets["delay_before"] = SliderRow(
            body, 2, "Countdown", self.delay_before, is_int=True, from_=0, to=10, step=1,
            tooltip="Seconds before drawing begins. Use them to switch to your target app.")

        label = ctk.CTkLabel(body, text="Button", text_color=theme.TEXT_2, anchor="w")
        label.grid(row=3, column=0, sticky="w", pady=(10, 3))
        Tooltip(label, "Which button to hold while drawing. Some apps draw with the left button, some with the right.")
        Segmented(body, [("left", "Left"), ("right", "Right")], self.mouse_button).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=(10, 3))

        label = ctk.CTkLabel(body, text="Position", text_color=theme.TEXT_2, anchor="w")
        label.grid(row=4, column=0, sticky="w", pady=(6, 0))
        Tooltip(label, "Start at the mouse pointer, or at fixed screen coordinates (set them by hand or with Pick area).")
        Segmented(body, [(True, "At pointer"), (False, "Fixed")], self.relative_offset).grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=(6, 0))

        self._position_hint = ctk.CTkLabel(body, text="", text_color=theme.MUTED, anchor="w", font=theme.font(12), wraplength=SIDEBAR_WIDTH - 60, justify="left")
        self._position_hint.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        self._fixed_row = ctk.CTkFrame(body, fg_color="transparent")
        self._fixed_row.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(6, 0))

        validate = (self.root.register(lambda text: text in ("", "-") or text.lstrip("-").isdigit()), "%P")

        for column, (axis, var) in enumerate((("X", self.offset_x), ("Y", self.offset_y))):
            ctk.CTkLabel(self._fixed_row, text=axis, text_color=theme.MUTED, width=14).grid(row=0, column=column * 2, padx=(0 if column == 0 else 10, 6))
            entry = ctk.CTkEntry(self._fixed_row, textvariable=var, width=70, height=30, justify="right", font=theme.mono_font(12), validate="key", validatecommand=validate)
            entry.grid(row=0, column=column * 2 + 1)
            Tooltip(entry, f"Absolute screen pixel {axis} of the drawing's top-left corner.")

        button(body, "Pick area on screen…", self._pick_canvas, height=30).grid(row=7, column=0, columnspan=3, sticky="ew", pady=(12, 0))

    def _build_actions(self, side):
        actions = ctk.CTkFrame(side, fg_color="transparent", corner_radius=0)
        actions.grid(row=1, column=0, sticky="ew", padx=(10, 16), pady=(4, 14))
        actions.columnconfigure(0, weight=1)

        self._btn_start = button(actions, "Start drawing", self._on_start_button, kind="primary", height=42, font=theme.font(14, "bold"))
        self._btn_start.grid(row=0, column=0, sticky="ew")
        self._btn_cancel = button(actions, "Cancel", self._cancel, kind="danger", height=42, width=96)
        self._btn_cancel.grid(row=0, column=1, padx=(8, 0))
        self._btn_cancel.grid_remove()

        self._progress_bar = ctk.CTkProgressBar(actions, height=6)
        self._progress_bar.set(0)
        self._progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._progress_bar.grid_remove()

        hints = ctk.CTkFrame(actions, fg_color="transparent")
        hints.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        self._kbd_start = kbd(hints, key_label(self._start_key_name))
        self._kbd_start.pack(side="left")
        ctk.CTkLabel(hints, text=" start / pause", text_color=theme.MUTED, font=theme.font(12)).pack(side="left", padx=(0, 14))
        self._kbd_stop = kbd(hints, key_label(self._stop_key_name))
        self._kbd_stop.pack(side="left")
        ctk.CTkLabel(hints, text=" cancel", text_color=theme.MUTED, font=theme.font(12)).pack(side="left")

    def _build_preview(self):
        pane = Card(self.root)
        pane.grid(row=2, column=1, sticky="nsew", padx=(8, 16), pady=(10, 14))
        pane.rowconfigure(1, weight=1)
        pane.body.grid_forget()

        head = ctk.CTkFrame(pane, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        head.columnconfigure(4, weight=1)
        ctk.CTkLabel(head, text="Preview", font=theme.font(14, "bold")).grid(row=0, column=0, padx=(0, 12))
        self._pill_contours = Pill(head)
        self._pill_contours.grid(row=0, column=1, padx=(0, 6))
        self._pill_points = Pill(head)
        self._pill_points.grid(row=0, column=2, padx=(0, 6))
        self._pill_size = Pill(head)
        self._pill_size.grid(row=0, column=3)

        live = ctk.CTkFrame(head, fg_color="transparent")
        live.grid(row=0, column=5, padx=(8, 4))
        live_label = ctk.CTkLabel(live, text="Live", text_color=theme.TEXT_2)
        live_label.pack(side="left", padx=(0, 6))
        Tooltip(live_label, "Re-detect contours automatically when a setting changes.")
        Toggle(live, self.auto_preview).pack(side="left")
        button(head, "Refresh", lambda: self._refresh_preview(), kind="ghost", width=74, height=28).grid(row=0, column=6, padx=2)
        button(head, "Pop out", self._open_preview, kind="ghost", width=74, height=28).grid(row=0, column=7)

        well = ctk.CTkFrame(pane, fg_color=theme.SURFACE_2, corner_radius=theme.RADIUS)
        well.grid(row=1, column=0, sticky="nsew", padx=16)
        self._preview_view = PreviewCanvas(well)
        self._preview_view.canvas.pack(fill="both", expand=True, padx=6, pady=6)

        canvas = self._preview_view.canvas
        self._empty_open = button(canvas, "Open image…", self._browse, kind="primary", width=130, bg_color=theme.SURFACE_2)
        self._empty_paste = button(canvas, "Paste", self._paste_from_clipboard, width=90, bg_color=theme.SURFACE_2)
        self._empty_svg = button(canvas, "Open SVG…", self._browse_svg, kind="primary", width=120, bg_color=theme.SURFACE_2)

        foot = ctk.CTkFrame(pane, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 12))
        foot.columnconfigure(0, weight=1)
        self.lbl_status = ctk.CTkLabel(foot, text="Load an image to begin.", text_color=theme.TEXT_2, anchor="w", justify="left")
        self.lbl_status.grid(row=0, column=0, sticky="ew")
        foot.bind("<Configure>", lambda e: self.lbl_status.configure(wraplength=max(200, e.width - 20)))

    def _bind_keys(self):
        self.root.bind_all("<Escape>", lambda e: self._cancel())
        self.root.bind_all("<Control-v>", self._on_ctrl_v)
        self.root.bind_all("<Control-o>", lambda e: self._browse())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        if sys.platform == "darwin":
            self.root.bind_all("<Command-v>", self._on_ctrl_v)
            self.root.bind_all("<Command-o>", lambda e: self._browse())
            self.root.createcommand("tk::mac::Quit", self._quit)
            self.root.createcommand("tkAboutDialog", self._show_about)
            self.root.createcommand("tk::mac::ShowPreferences", self._show_keybinds)

    def _on_text_ctrl_o(self, event):
        self._browse()

        # Stops Tk's Text class binding, which would insert a newline, and the global Ctrl+O binding.
        return "break"

    def _browse(self):
        path = ask_open_filename(self.root, "Open image or SVG", IMAGE_TYPES)

        if not path:
            return

        if path.lower().endswith(".svg"):
            self._load_svg(path)
        else:
            self._load_image(path)

    def _load_image(self, path):
        gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

        if gray is None:
            self._update_status("Could not read that image.")
            return

        self._set_mode("image")
        self.image_path = path
        self.gray_image = gray
        self.lbl_file.configure(text=os.path.basename(path))
        self._image_bounds = None
        self._do_crop()

    def _load_svg(self, path):
        try:
            contours = load_svg(path)
        except Exception as e:
            self._update_status(f"SVG error: {e}")
            return

        if not contours:
            self._update_status("No paths found in SVG.")
            return

        self._set_mode("textsvg")
        self._textsvg_contours, self._textsvg_bounds = self._normalized(contours)
        self._svg_name = os.path.basename(path)
        self._lbl_svg.configure(text=f"{self._svg_name}  ·  {self._textsvg_bounds[0]:.0f} × {self._textsvg_bounds[1]:.0f}", text_color=theme.TEXT)

        self._update_status(f"Loaded SVG with {len(self._textsvg_contours)} paths.")
        self._refresh_preview(extract=False)

    @staticmethod
    def _normalized(contours):
        """Contours shifted so their bounding box starts at the origin, plus that box's (width, height)."""
        all_pts = np.vstack(contours)
        mins = all_pts.min(axis=0)
        maxs = all_pts.max(axis=0)

        return [c - mins for c in contours], (maxs[0] - mins[0], maxs[1] - mins[1])

    def _recrop(self):
        if self.gray_image is None:
            self._update_status("No image loaded.")
            return

        self._do_crop()

    def _do_crop(self):
        auto_rect = detect_art_bounds(self.gray_image)
        dialog = CropDialog(self.root, self.gray_image, auto_rect=auto_rect)

        if dialog.result == "CANCEL":
            return

        h, w = self.gray_image.shape

        if dialog.result is None:
            self.cropped_image = self.gray_image.copy()
            self.lbl_crop.configure(text=f"Full image · {w} × {h} px")
        else:
            x, y, cw, ch = dialog.result
            self.cropped_image = self.gray_image[y:y + ch, x:x + cw].copy()
            self.lbl_crop.configure(text=f"Cropped to {cw} × {ch} px at ({x}, {y}) of {w} × {h}")

        if not self._restoring_session:
            self._apply_suggested()

        self._refresh_preview()

    def _apply_suggested(self):
        if self.cropped_image is None:
            return

        s = compute_suggested(self.cropped_image)
        self.btn_suggested.configure(state="normal")

        self.detect_mode.set(s["detect_mode"])
        self.threshold.set(s["threshold"])
        self.min_contour_len.set(s["min_contour_len"])
        self.simplify.set(s["simplify"])
        self.blur_radius.set(s["blur_radius"])
        self.morph_iter.set(s["morph_iter"])
        self.canny_lo.set(s["canny_lo"])
        self.canny_hi.set(s["canny_hi"])
        self.adaptive_block.set(s["adaptive_block"])
        self.adaptive_c.set(s["adaptive_c"])
        self.use_skeleton.set(False)

        self.root.after(10, self._sync_all_widgets)
        self.root.after(10, self._update_mode_visibility)

        self._update_status(
            f"Suggested settings: {s['detect_mode']}, threshold {s['threshold']}, blur {s['blur_radius']}, "
            f"min length {s['min_contour_len']}, simplify {s['simplify']} (ink {s['ink_ratio']:.1%}, sharpness {s['lap_var']:.0f}).")

    def _extract_contours(self):
        if self.cropped_image is None:
            return

        self._image_contours = extract_contours(
            self.cropped_image,
            mode=self.detect_mode.get(),
            threshold=self.threshold.get(),
            canny_lo=self.canny_lo.get(),
            canny_hi=self.canny_hi.get(),
            adaptive_block=self.adaptive_block.get(),
            adaptive_c=self.adaptive_c.get(),
            blur_radius=self.blur_radius.get(),
            morph_iterations=self.morph_iter.get(),
            min_length=self.min_contour_len.get(),
            epsilon=self.simplify.get(),
            use_skeleton=self.use_skeleton.get(),
        )

    def _open_preview(self):
        if self.preview is None or not self.preview.is_open():
            self.preview = PreviewWindow(self.root)

        self._refresh_preview(extract=False)

        if not self.contours:
            self.preview.render([], 1.0, (1, 1))

        self.preview.focus()

    def _browse_svg(self):
        path = ask_open_filename(self.root, "Open SVG", [("SVG files", "*.svg"), ("All files", "*.*")])

        if path:
            self._load_svg(path)

    def _on_appearance_change(self, mode):
        self._preview_view.refresh_theme()
        self._font_picker.refresh_theme()

        if self.preview and self.preview.is_open():
            self.preview.refresh_theme()

    def _show_keybinds(self):
        self._polling_paused = True
        dlg = KeybindsDialog(self.root, self.config, self._on_keybind_update)
        dlg.win.bind("<Destroy>", lambda e: setattr(self, "_polling_paused", False) if e.widget is dlg.win else None)

    def _on_keybind_update(self, config_key, key_name):
        keycode = resolve_keycode(key_name)

        if keycode is None:
            self._update_status(f"Key '{key_name}' is not supported.")
            return False

        if config_key == "start_key":
            self._start_keycode = keycode
            self._start_key_name = key_name
            self._kbd_start.configure(text=key_label(key_name))
        elif config_key == "stop_key":
            self.draw_engine._cancel_check = lambda: is_key_pressed(keycode)
            self._stop_key_name = key_name
            self._kbd_stop.configure(text=key_label(key_name))

        self._update_status(f"{'Start / pause' if config_key == 'start_key' else 'Cancel'} key set to {key_label(key_name)}.")

        return True

    def _poll(self):
        if not self._polling_paused and self._start_keycode is not None:
            pressed = is_key_pressed(self._start_keycode)

            if pressed and not self._start_key_was_pressed:
                self._on_start_button()

            self._start_key_was_pressed = pressed

        self._sync_engine_state()
        self.root.after(30, self._poll)

    def _on_start_button(self):
        state = self.draw_engine.state

        if state == "idle":
            self._start_drawing()
        elif state == "drawing":
            self.draw_engine.pause()
        elif state == "paused":
            self.draw_engine.resume()

    def _sync_engine_state(self):
        state = self.draw_engine.state
        done, total = self._progress

        if state != "idle" and total and done / total != self._progress_shown:
            self._progress_shown = done / total
            self._progress_bar.set(self._progress_shown)

        if state == self._engine_state:
            return

        self._engine_state = state
        start = key_label(self._start_key_name)

        if state == "idle":
            self._btn_start.configure(text="Start drawing")
            self._btn_cancel.grid_remove()
            self._progress_bar.grid_remove()
            self._state_pill.set("Ready")
        elif state == "drawing":
            self._btn_start.configure(text=f"Pause  ({start})")
            self._btn_cancel.grid()
            self._progress_bar.grid()
            self._state_pill.set("Drawing", "accent")
        else:
            self._btn_start.configure(text=f"Resume  ({start})")
            self._state_pill.set("Paused", "warn")

    def _on_progress(self, done, total):
        self._progress = (done, total)

    def _start_drawing(self):
        if accessibility.needs_permission() and not accessibility.is_trusted():
            self._show_accessibility()
            return

        if not self.contours and self.input_mode == "image":
            self._extract_contours()

        if not self.contours:
            self._update_status("No contours to draw. Load an image, an SVG or some text first.")
            return

        draw_contours = list(self.contours)

        if self.optimize_path.get() and len(draw_contours) > 1:
            draw_contours, reduction = optimize_path(draw_contours)
            self._update_status(f"Optimized: travel reduced by {reduction:.0%}")

        params = {
            "mouse_button": self.mouse_button.get(),
            "speed": self.speed.get(),
            "offset_x": self._int(self.offset_x, 200),
            "offset_y": self._int(self.offset_y, 200),
            "scale": self.scale.get(),
            "relative_to_mouse": self.relative_offset.get(),
            "delay_before_start": self.delay_before.get(),
            "start_key_label": key_label(self._start_key_name),
            "stop_key_label": key_label(self._stop_key_name),
        }

        self._progress = (0, sum(len(c) for c in draw_contours))
        self._progress_shown = 0
        self._progress_bar.set(0)

        threading.Thread(target=self.draw_engine.run, args=(draw_contours, params), daemon=True).start()

    @staticmethod
    def _int(var, fallback):
        try:
            return int(var.get())
        except (ValueError, tk.TclError):
            return fallback

    def _on_ctrl_v(self, event):
        if isinstance(event.widget, (tk.Text, tk.Entry)):
            return

        self._paste_from_clipboard()

    def _update_status(self, text):
        self.root.after(0, lambda: self.lbl_status.configure(text=text))

    def _cancel(self):
        self.draw_engine.cancel()

    def _show_about(self):
        AboutDialog(self.root)

    def _check_accessibility(self):
        if accessibility.is_trusted():
            self._access_button.grid_remove()
            return

        self._access_button.grid()

        if not self.config.get("accessibility_prompted"):
            self.config["accessibility_prompted"] = True
            save_config(self.config)
            self._show_accessibility()

        self.root.after(3000, self._check_accessibility)

    def _show_accessibility(self):
        if self._accessibility_dialog and self._accessibility_dialog.win.winfo_exists():
            self._accessibility_dialog.win.lift()
            return

        self._accessibility_dialog = AccessibilityDialog(self.root, on_granted=self._access_button.grid_remove)

    def _paste_from_clipboard(self):
        img = get_clipboard_image()

        if img is None:
            self._update_status("No image in the clipboard.")
            return

        rgb = np.array(img.convert("RGB"))

        self._set_mode("image")
        self.gray_image = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        self.image_path = "(clipboard)"
        self.lbl_file.configure(text="Pasted image")
        self._do_crop()

    def _populate_fonts(self, refresh=False):
        if self._fonts_loading:
            return

        self._fonts_loading = True
        self._lbl_font.configure(text="Loading fonts…")

        def work():
            fonts = discover_fonts(refresh=refresh)

            try:
                self.root.after(0, lambda: self._apply_fonts(fonts))
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _apply_fonts(self, fonts):
        self._fonts_loading = False
        self._font_list = fonts
        families = sorted(set(f["family"] for f in fonts), key=str.lower)
        self._font_picker.set_families(families)

        if self.font_path:
            current = next((f["family"] for f in fonts if f["path"] == self.font_path), None)

            if current:
                self._font_picker.select(current)

            self._lbl_font.configure(text=current or os.path.basename(self.font_path))

            return

        if not families:
            self._lbl_font.configure(text="No fonts found. Use Font file…")
            return

        default = next((f for f in PREFERRED_FONTS if f in families), families[0])
        self._font_picker.select(default)
        self._on_font_change(default)

    def _browse_font(self):
        path = ask_open_filename(self.root, "Open font", [("Font files", "*.ttf *.otf"), ("All files", "*.*")])

        if path:
            self.font_path = path
            self._lbl_font.configure(text=os.path.basename(path))
            self._on_text_change()

    def _on_font_change(self, family):
        path = regular_path(self._font_list, family)

        if not path:
            return

        self.font_path = path
        self._lbl_font.configure(text=family)
        self._on_text_change()

    def _schedule_text_change(self):
        if self._text_timer is not None:
            self.root.after_cancel(self._text_timer)

        self._text_timer = self.root.after(150, self._on_text_change)

    def _on_text_change(self):
        self._text_timer = None
        text = self._text_box.get("1.0", "end-1c").strip()

        if not text and self._svg_name is None and self._textsvg_contours:
            self._textsvg_contours = []
            self._textsvg_bounds = None
            self._update_status("Text cleared.")
            self._refresh_preview(extract=False)
            return

        if not text or not self.font_path:
            return

        max_w = None

        if self._textsvg_bounds and self._svg_name:
            max_w = self._textsvg_bounds[0]

        try:
            contours = render_text(text, self.font_path, self.font_size.get(), max_width=max_w)
        except Exception as e:
            self._update_status(f"Text error: {e}")
            return

        if not contours:
            self._update_status("No glyphs rendered.")
            return

        self._textsvg_contours, self._textsvg_bounds = self._normalized(contours)
        self._svg_name = None
        self._lbl_svg.configure(text="No SVG loaded", text_color=theme.MUTED)

        total_points = sum(len(c) for c in self._textsvg_contours)
        self._update_status(f"Text rendered: {len(self._textsvg_contours)} contours, {total_points} points.")
        self._refresh_preview(extract=False)

    def _pick_canvas(self):
        if self._current_shape() is None or not self.contours:
            self._update_status("Load an image, an SVG or some text first.")
            return

        CanvasPicker(self.root, self._apply_canvas_target)

    def _apply_canvas_target(self, x, y, width, height):
        shape = self._current_shape()

        if shape is None:
            return

        img_h, img_w = shape
        # Rounded down to the scale field's two decimals, so the drawing still fits once the field re-commits it.
        scale = max(0.01, math.floor(min(width / img_w, height / img_h) * 100) / 100)

        self.offset_x.set(str(x))
        self.offset_y.set(str(y))
        self.relative_offset.set(False)
        self.scale.set(scale)
        self._widgets["scale"].sync()
        self._update_status(f"Canvas set: {width} × {height} at ({x}, {y}), scale {self.scale.get():.2f}.")

    def _self_test(self):
        square = [np.array([[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]], dtype=np.float64)]
        render_preview(square, 1.0, (100, 100), 320, 240)
        self._preview_view.show(square, 1.0, (100, 100))
        self.root.update()
        AboutDialog(self.root).win.destroy()

        print(f"Inkspire self-test OK (Tk {self.root.tk.call('info', 'patchlevel')}, {ctk.get_appearance_mode()} mode)")
        self.root.destroy()

    def _quit(self):
        offset_x = self._int(self.offset_x, 200)
        offset_y = self._int(self.offset_y, 200)

        self.config.update({
            "scale": self.scale.get(),
            "offset_x": offset_x,
            "offset_y": offset_y,
            "speed": self.speed.get(),
            "mouse_button": self.mouse_button.get(),
            "delay_before": self.delay_before.get(),
            "relative_offset": self.relative_offset.get(),
            "auto_preview": self.auto_preview.get(),
            "optimize_path": self.optimize_path.get(),
            "start_key": self._start_key_name,
            "stop_key": self._stop_key_name,
        })
        save_config(self.config)
        save_session({
            "source_path": self.image_path,
            "input_tab": 0 if self.input_mode == "image" else 1,
            "detection_settings": {
                "mode": self.detect_mode.get(),
                "threshold": self.threshold.get(),
                "canny_lo": self.canny_lo.get(),
                "canny_hi": self.canny_hi.get(),
                "adaptive_block": self.adaptive_block.get(),
                "adaptive_c": self.adaptive_c.get(),
                "blur_radius": self.blur_radius.get(),
                "morph_iter": self.morph_iter.get(),
                "min_contour_len": self.min_contour_len.get(),
                "simplify": self.simplify.get(),
                "skeleton": self.use_skeleton.get(),
            },
            "drawing_settings": {
                "scale": self.scale.get(),
                "offset_x": offset_x,
                "offset_y": offset_y,
                "speed": self.speed.get(),
                "mouse_button": self.mouse_button.get(),
                "delay_before": self.delay_before.get(),
                "relative_offset": self.relative_offset.get(),
                "auto_preview": self.auto_preview.get(),
                "optimize_path": self.optimize_path.get(),
            },
            "text_content": self._text_box.get("1.0", "end-1c"),
            "font_path": self.font_path,
            "font_size": self.font_size.get(),
        })

        self.root.destroy()
        sys.exit(0)


def main():
    Inkspire(self_test="--self-test" in sys.argv)


if __name__ == "__main__":
    main()

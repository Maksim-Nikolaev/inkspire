#!/usr/bin/env python3
"""
Inkspire – traces line art by moving the mouse along extracted contours.
Uses ctypes X11 calls for fast, jitter-free mouse control.

Supports: B/W line art, colored images, halftones via multiple detection modes.

Usage: python3 main.py

Requires: opencv-python, numpy, Pillow
Install:  sudo pip install opencv-python numpy Pillow --break-system-packages
System:   sudo apt install python3-tk python3-pil.imagetk
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import threading
import time
import sys
from detection.modes import detect_art_bounds, detect_edges
from detection.contours import extract_contours, skeletonize
from detection.suggest import compute_suggested
from detection.svg import load_svg
from detection.text import render_text
from core.fonts import discover_fonts
from drawing.engine import DrawEngine
from ui.about_dialog import AboutDialog
from ui.crop_dialog import CropDialog
from ui.tooltip import Tooltip
from ui.widgets import LinkedSliderEntry
from ui.preview import PreviewWindow
from ui.canvas_picker import CanvasPicker
from core.config import load_config, save_config
from core.keybinds import resolve_keycode
from drawing.mouse_x11 import is_key_pressed

MODES = ["Threshold", "Canny Edge", "Adaptive Threshold", "Auto"]

# ── Main GUI ──

class Inkspire:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Inkspire")
        self.root.resizable(False, False)

        self.image_path = None
        self.gray_image = None
        self.cropped_image = None
        self.contours = []
        self._preview_timer = None
        self.config = load_config()
        stop_keycode = resolve_keycode(self.config.get("stop_key", "Escape"))
        cancel_check = (lambda: is_key_pressed(stop_keycode)) if stop_keycode else None
        self.draw_engine = DrawEngine(on_status=self._update_status, cancel_check=cancel_check)

        self._widgets: dict[str, LinkedSliderEntry] = {}

        # Detection mode
        self.detect_mode = tk.StringVar(value="Auto")

        # Settings (drawing settings loaded from config, detection defaults are fixed)
        cfg = self.config
        self.scale = tk.DoubleVar(value=cfg.get("scale", 1.0))
        self.offset_x = tk.IntVar(value=cfg.get("offset_x", 200))
        self.offset_y = tk.IntVar(value=cfg.get("offset_y", 200))
        self.speed = tk.DoubleVar(value=cfg.get("speed", 0.02))
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

        self.input_mode = "image"  # "image", "svg", or "text"
        self.contour_bounds = None  # (width, height) for SVG/text contours

        self.text_input = tk.StringVar(value="")
        self.font_size = tk.DoubleVar(value=48.0)
        self.font_path = None
        self._font_list = []

        self.preview = None

        self._build_gui()
        self.root.bind_all("<Escape>", lambda e: self._cancel())
        self.root.bind_all("<Control-v>", lambda e: self._paste_from_clipboard())
        self._setup_traces()
        self._update_mode_visibility()

        # Global hotkey polling (works even when another app has focus)
        start_keycode = resolve_keycode(self.config.get("start_key", "F5"))
        self._start_keycode = start_keycode
        self._start_key_was_pressed = False
        if start_keycode:
            self._poll_start_key()

        self.root.mainloop()

    def _sync_all_widgets(self):
        for w in self._widgets.values():
            w.sync()

    def _set_widget_visible(self, var_name, visible):
        self._widgets[var_name].set_visible(visible)

    # ── Mode-dependent visibility ──

    def _update_mode_visibility(self):
        mode = self.detect_mode.get()

        # Threshold params
        self._set_widget_visible("threshold", mode in ("Threshold", "Auto"))
        # Canny params
        self._set_widget_visible("canny_lo", mode in ("Canny Edge", "Auto"))
        self._set_widget_visible("canny_hi", mode in ("Canny Edge", "Auto"))
        # Adaptive params
        self._set_widget_visible("adaptive_block", mode in ("Adaptive Threshold", "Auto"))
        self._set_widget_visible("adaptive_c", mode in ("Adaptive Threshold", "Auto"))

    def _update_input_mode_visibility(self):
        show_detection = self.input_mode == "image"
        for frame in (self._frame_mode, self._frame_det, self._frame_proc, self._frame_cont):
            frame.pack_forget()
        self._frame_draw.pack_forget()
        self.lbl_status.pack_forget()
        self.lbl_contours.pack_forget()
        self.lbl_crop.pack_forget()
        self._frame_btn.pack_forget()

        pad = {"padx": 6, "pady": 3}
        if show_detection:
            for frame in (self._frame_mode, self._frame_det, self._frame_proc, self._frame_cont):
                frame.pack(fill="x", **pad)
        self._frame_draw.pack(fill="x", **pad)
        self.lbl_status.pack(**pad)
        self.lbl_contours.pack(**pad)
        self.lbl_crop.pack(**pad)
        self._frame_btn.pack(fill="x", **pad)

    # ── Traces for live preview ──

    def _setup_traces(self):
        live_vars = [
            self.threshold, self.min_contour_len, self.simplify, self.scale,
            self.canny_lo, self.canny_hi, self.adaptive_block, self.adaptive_c,
            self.blur_radius, self.morph_iter,
        ]
        for var in live_vars:
            var.trace_add("write", lambda *_: self._schedule_preview_update())
        self.use_skeleton.trace_add("write", lambda *_: self._schedule_preview_update())
        self.detect_mode.trace_add("write", lambda *_: self._on_mode_change())
        self.font_size.trace_add("write", lambda *_: self._on_text_change())

    def _on_mode_change(self):
        self._update_mode_visibility()
        self._schedule_preview_update()

    def _schedule_preview_update(self):
        if not self.auto_preview.get():
            return
        if self.input_mode == "image" and self.cropped_image is None:
            return
        if self._preview_timer is not None:
            self.root.after_cancel(self._preview_timer)
        self._preview_timer = self.root.after(300, self._update_live_preview)

    def _update_live_preview(self):
        self._preview_timer = None
        if self.input_mode == "image":
            self._extract_contours()
        if self.preview and self.preview.is_open():
            if self.input_mode == "image" and self.cropped_image is not None:
                shape = self.cropped_image.shape[:2]
            elif self.contour_bounds:
                shape = (int(self.contour_bounds[1]), int(self.contour_bounds[0]))
            else:
                return
            self.preview.render(self.contours, self.scale.get(), shape)

    # ── GUI build ──

    def _build_gui(self):
        pad = {"padx": 6, "pady": 3}

        # ── File ──
        frame_file = ttk.LabelFrame(self.root, text="Image")
        frame_file.pack(fill="x", **pad)
        self.lbl_file = ttk.Label(frame_file, text="No file selected")
        self.lbl_file.pack(side="left", **pad)
        ttk.Button(frame_file, text="Re-crop", command=self._recrop).pack(side="right", **pad)
        ttk.Button(frame_file, text="Browse", command=self._browse).pack(side="right", **pad)
        ttk.Button(frame_file, text="Paste", command=self._paste_from_clipboard).pack(side="right", **pad)

        # ── Text Input ──
        self._frame_text = ttk.LabelFrame(self.root, text="Text to Draw")
        self._frame_text.pack(fill="x", **pad)

        self._text_box = tk.Text(self._frame_text, height=3, width=40, wrap="word")
        self._text_box.pack(fill="x", **pad)
        self._text_box.bind("<KeyRelease>", lambda e: self._on_text_change())

        font_row = ttk.Frame(self._frame_text)
        font_row.pack(fill="x", **pad)
        ttk.Label(font_row, text="Font:").pack(side="left")
        self._font_combo = ttk.Combobox(font_row, state="readonly", width=30)
        self._font_combo.pack(side="left", padx=4)
        self._font_combo.bind("<<ComboboxSelected>>", lambda e: self._on_font_change())
        ttk.Button(font_row, text="Browse...", command=self._browse_font).pack(side="left", padx=4)

        size_row = ttk.Frame(self._frame_text)
        size_row.pack(fill="x", **pad)
        self._widgets["font_size"] = LinkedSliderEntry(
            size_row, 0, "Size (px):", self.font_size, "font_size",
            is_int=False, from_=8, to=200, step=1, pad=pad,
            tooltip="Font size in pixels. Controls glyph height.")

        # Populate fonts in background (first scan can be slow)
        self.root.after(100, self._populate_fonts)

        # ── Detection Mode ──
        self._frame_mode = ttk.LabelFrame(self.root, text="Detection Mode")
        self._frame_mode.pack(fill="x", **pad)

        mode_row = ttk.Frame(self._frame_mode)
        mode_row.pack(fill="x", **pad)
        for m in MODES:
            ttk.Radiobutton(mode_row, text=m, variable=self.detect_mode, value=m).pack(side="left", padx=4)

        # ── Detection Parameters ──
        self._frame_det = ttk.LabelFrame(self.root, text="Detection Parameters")
        self._frame_det.pack(fill="x", **pad)

        row = 0
        self._widgets["threshold"] = LinkedSliderEntry(
            self._frame_det, row, "Threshold (1-254):", self.threshold, "threshold",
            is_int=True, from_=1, to=254, step=1, pad=pad,
            tooltip="Brightness cutoff (0=black, 255=white). Pixels darker than this become edges. Lower = more detected. Otsu auto-picks the optimal split.")
        row += 1
        self._widgets["canny_lo"] = LinkedSliderEntry(
            self._frame_det, row, "Canny low:", self.canny_lo, "canny_lo",
            is_int=True, from_=1, to=300, step=1, pad=pad,
            tooltip="Minimum gradient strength to start an edge. Lower = more edges, more noise. Typical: 30-100.")
        row += 1
        self._widgets["canny_hi"] = LinkedSliderEntry(
            self._frame_det, row, "Canny high:", self.canny_hi, "canny_hi",
            is_int=True, from_=1, to=500, step=1, pad=pad,
            tooltip="Minimum gradient strength to confirm an edge. Lower = more connected edges. Typical: 100-250. Keep > Canny low.")
        row += 1
        self._widgets["adaptive_block"] = LinkedSliderEntry(
            self._frame_det, row, "Adaptive block size:", self.adaptive_block, "adaptive_block",
            is_int=True, from_=3, to=99, step=2, pad=pad,
            tooltip="Size of the local neighborhood for threshold calculation. Must be odd. Larger = smoother, less sensitive to small features. Typical: 7-21.")
        row += 1
        self._widgets["adaptive_c"] = LinkedSliderEntry(
            self._frame_det, row, "Adaptive C:", self.adaptive_c, "adaptive_c",
            is_int=True, from_=-20, to=20, step=1, pad=pad,
            tooltip="Constant subtracted from the local mean. Higher = fewer edges detected. Typical: 0-10.")

        self._frame_det.columnconfigure(1, weight=1)

        # ── Pre/Post Processing ──
        self._frame_proc = ttk.LabelFrame(self.root, text="Pre/Post Processing")
        self._frame_proc.pack(fill="x", **pad)

        row = 0
        self._widgets["blur_radius"] = LinkedSliderEntry(
            self._frame_proc, row, "Blur radius (halftone):", self.blur_radius, "blur_radius",
            is_int=True, from_=0, to=20, step=1, pad=pad,
            tooltip="Gaussian blur kernel radius applied before detection. Removes halftone dots and noise. 0 = off. For halftones try 2-5.")
        row += 1
        self._widgets["morph_iter"] = LinkedSliderEntry(
            self._frame_proc, row, "Morph cleanup (iter):", self.morph_iter, "morph_iter",
            is_int=True, from_=0, to=10, step=1, pad=pad,
            tooltip="Morphological operations to clean up the edge mask. Close fills small gaps, open removes specks. 0 = off. 1-2 = light cleanup.")

        self._frame_proc.columnconfigure(1, weight=1)

        # ── Contour Settings ──
        self._frame_cont = ttk.LabelFrame(self.root, text="Contour Settings")
        self._frame_cont.pack(fill="x", **pad)

        row = 0
        self._widgets["min_contour_len"] = LinkedSliderEntry(
            self._frame_cont, row, "Min contour length:", self.min_contour_len, "min_contour_len",
            is_int=True, from_=1, to=500, step=1, pad=pad,
            tooltip="Contours shorter than this (in points) are discarded. Filters out noise fragments. Higher = cleaner but may lose small details.")
        row += 1
        self._widgets["simplify"] = LinkedSliderEntry(
            self._frame_cont, row, "Simplify (epsilon):", self.simplify, "simplify",
            is_int=False, from_=0.1, to=10.0, step=0.1, pad=pad,
            tooltip="How aggressively contour paths are simplified. Higher = fewer points, faster drawing, but corners get rounded. 0.5 = detailed, 2.0 = aggressive.")
        row += 1
        skel_cb = ttk.Checkbutton(self._frame_cont, text="Skeletonize (thin lines to 1px)",
                                  variable=self.use_skeleton)
        skel_cb.grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        Tooltip(skel_cb, "Thin all detected regions to 1px centerlines. Useful when source has thick brush strokes. Off by default.")
        row += 1
        self.btn_suggested = ttk.Button(self._frame_cont, text="Reset to Suggested",
                                        command=self._apply_suggested, state="disabled")
        self.btn_suggested.grid(row=row, column=0, columnspan=3, sticky="w", **pad)

        self._frame_cont.columnconfigure(1, weight=1)

        # ── Drawing Settings ──
        self._frame_draw = ttk.LabelFrame(self.root, text="Drawing Settings")
        self._frame_draw.pack(fill="x", **pad)

        row = 0
        self._widgets["scale"] = LinkedSliderEntry(
            self._frame_draw, row, "Scale:", self.scale, "scale",
            is_int=False, from_=0.10, to=10.0, step=0.01, pad=pad,
            tooltip="Multiply the image dimensions by this factor for drawing. 1.0 = original size. 2.0 = double size.")
        row += 1
        ttk.Label(self._frame_draw, text="Offset X (px):").grid(row=row, column=0, sticky="w", **pad)
        ox_entry = ttk.Entry(self._frame_draw, textvariable=self.offset_x, width=8)
        ox_entry.grid(row=row, column=1, sticky="w", **pad)
        Tooltip(ox_entry, "Absolute screen pixel X for the top-left corner of the drawn image.")

        row += 1
        ttk.Label(self._frame_draw, text="Offset Y (px):").grid(row=row, column=0, sticky="w", **pad)
        oy_entry = ttk.Entry(self._frame_draw, textvariable=self.offset_y, width=8)
        oy_entry.grid(row=row, column=1, sticky="w", **pad)
        Tooltip(oy_entry, "Absolute screen pixel Y for the top-left corner of the drawn image.")

        row += 1
        rel_cb = ttk.Checkbutton(self._frame_draw, text="Relative to mouse (bottom-left corner)",
                                 variable=self.relative_offset)
        rel_cb.grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        Tooltip(rel_cb, "When enabled, ignores Offset X/Y. Your mouse position at draw start becomes the bottom-left corner of the image.")

        row += 1
        self._widgets["speed"] = LinkedSliderEntry(
            self._frame_draw, row, "Speed (s/point):", self.speed, "speed",
            is_int=False, from_=0.0, to=0.1, step=0.001, pad=pad,
            tooltip="Delay in seconds between each point movement. Lower = faster. 0 = maximum speed. If the target app drops strokes, increase this.")

        row += 1
        ttk.Label(self._frame_draw, text="Mouse button:").grid(row=row, column=0, sticky="w", **pad)
        btn_frame = ttk.Frame(self._frame_draw)
        btn_frame.grid(row=row, column=1, sticky="w", **pad)
        ttk.Radiobutton(btn_frame, text="Left", variable=self.mouse_button, value="left").pack(side="left")
        ttk.Radiobutton(btn_frame, text="Right", variable=self.mouse_button, value="right").pack(side="left")
        Tooltip(btn_frame, "Which button to hold while drawing. Some apps use left, some use right for drawing tools.")

        row += 1
        ttk.Label(self._frame_draw, text="Delay before start (s):").grid(row=row, column=0, sticky="w", **pad)
        delay_entry = ttk.Entry(self._frame_draw, textvariable=self.delay_before, width=8)
        delay_entry.grid(row=row, column=1, sticky="w", **pad)
        Tooltip(delay_entry, "Seconds of countdown before drawing begins. Use this time to switch to your target application and position your mouse.")

        row += 1
        ttk.Button(self._frame_draw, text="Set Canvas", command=self._pick_canvas).grid(
            row=row, column=0, columnspan=3, sticky="w", **pad)

        self._frame_draw.columnconfigure(1, weight=1)

        # ── Status ──
        self.lbl_status = ttk.Label(self.root, text="Load an image to begin.")
        self.lbl_status.pack(**pad)
        self.lbl_contours = ttk.Label(self.root, text="")
        self.lbl_contours.pack(**pad)
        self.lbl_crop = ttk.Label(self.root, text="")
        self.lbl_crop.pack(**pad)

        # ── Buttons ──
        self._frame_btn = ttk.Frame(self.root)
        self._frame_btn.pack(fill="x", **pad)
        ttk.Button(self._frame_btn, text="Preview", command=self._open_preview).pack(side="left", **pad)
        ttk.Checkbutton(self._frame_btn, text="Live", variable=self.auto_preview).pack(side="left", **pad)
        ttk.Button(self._frame_btn, text="Start Drawing", command=self._start_drawing).pack(side="left", **pad)
        ttk.Button(self._frame_btn, text="About", command=self._show_about).pack(side="left", **pad)
        ttk.Button(self._frame_btn, text="Quit", command=self._quit).pack(side="right", **pad)

    # ── Image Loading, Crop, Auto-propose ──

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp *.svg"),
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                ("SVG", "*.svg"),
                ("All", "*.*"),
            ]
        )
        if not path:
            return
        if path.lower().endswith(".svg"):
            self._load_svg(path)
        else:
            self._load_image(path)

    def _load_image(self, path):
        self.image_path = path
        self.gray_image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if self.gray_image is None:
            self.lbl_status.config(text="Error: could not read image.")
            return
        self.lbl_file.config(text=path.split("/")[-1])
        self.input_mode = "image"
        self.contour_bounds = None
        self._update_input_mode_visibility()
        self._do_crop()

    def _load_svg(self, path):
        try:
            self.contours = load_svg(path)
        except Exception as e:
            self.lbl_status.config(text=f"SVG error: {e}")
            return
        if not self.contours:
            self.lbl_status.config(text="No paths found in SVG.")
            return
        self.image_path = path
        self.gray_image = None
        self.cropped_image = None
        self.input_mode = "svg"

        all_pts = np.vstack(self.contours)
        mins = all_pts.min(axis=0)
        maxs = all_pts.max(axis=0)
        self.contour_bounds = (maxs[0] - mins[0], maxs[1] - mins[1])
        for i, c in enumerate(self.contours):
            self.contours[i] = c - mins

        total_points = sum(len(c) for c in self.contours)
        self.lbl_file.config(text=path.split("/")[-1])
        self.lbl_contours.config(text=f"Contours: {len(self.contours)}, Total points: {total_points}")
        self.lbl_crop.config(text=f"SVG: {self.contour_bounds[0]:.0f}x{self.contour_bounds[1]:.0f}")
        self._update_input_mode_visibility()
        self._update_status(f"Loaded SVG with {len(self.contours)} paths.")
        if self.auto_preview.get():
            self._open_preview()

    def _recrop(self):
        if self.gray_image is None:
            self.lbl_status.config(text="No image loaded.")
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
            self.lbl_crop.config(text=f"Crop: full image ({w}x{h}px)")
        else:
            x, y, cw, ch = dialog.result
            self.cropped_image = self.gray_image[y:y + ch, x:x + cw].copy()
            self.lbl_crop.config(text=f"Crop: ({x},{y}) {cw}x{ch}px from {w}x{h}px original")

        self._apply_suggested()
        self._extract_contours()
        if self.auto_preview.get():
            self._open_preview()

    def _apply_suggested(self):
        if self.cropped_image is None:
            return
        s = compute_suggested(self.cropped_image)
        self.btn_suggested.config(state="normal")

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

        self.lbl_status.config(
            text=f"Suggested: mode={s['detect_mode']}, thresh={s['threshold']}, "
                 f"blur={s['blur_radius']}, min_len={s['min_contour_len']}, "
                 f"eps={s['simplify']} (ink:{s['ink_ratio']:.1%} lap:{s['lap_var']:.0f})")

    # ── Contour Extraction ──

    def _extract_contours(self):
        if self.cropped_image is None:
            return

        self.contours = extract_contours(
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

        total_points = sum(len(c) for c in self.contours)
        self.lbl_contours.config(text=f"Contours: {len(self.contours)}, Total points: {total_points}")

    def _skeletonize(self, binary):
        return skeletonize(binary)

    # ── Preview ──

    def _open_preview(self):
        if self.input_mode == "image":
            self._extract_contours()
        if not self.contours:
            self.lbl_status.config(text="No contours found. Adjust parameters.")
            return
        if self.preview is None or not self.preview.is_open():
            self.preview = PreviewWindow(self.root)
        if self.input_mode == "image" and self.cropped_image is not None:
            shape = self.cropped_image.shape[:2]
        elif self.contour_bounds:
            shape = (int(self.contour_bounds[1]), int(self.contour_bounds[0]))
        else:
            all_pts = np.vstack(self.contours)
            maxs = all_pts.max(axis=0)
            shape = (int(maxs[1]) + 1, int(maxs[0]) + 1)
        self.preview.render(self.contours, self.scale.get(), shape)

    # ── Drawing ──

    def _poll_start_key(self):
        pressed = is_key_pressed(self._start_keycode)
        if pressed and not self._start_key_was_pressed:
            self._start_drawing()
        self._start_key_was_pressed = pressed
        self.root.after(100, self._poll_start_key)

    def _start_drawing(self):
        if not self.contours and self.input_mode == "image":
            self._extract_contours()
        if not self.contours:
            self.lbl_status.config(text="No contours to draw.")
            return
        params = {
            "mouse_button": self.mouse_button.get(),
            "speed": self.speed.get(),
            "offset_x": self.offset_x.get(),
            "offset_y": self.offset_y.get(),
            "scale": self.scale.get(),
            "relative_to_mouse": self.relative_offset.get(),
            "delay_before_start": self.delay_before.get(),
        }
        threading.Thread(target=self.draw_engine.run, args=(self.contours, params), daemon=True).start()

    def _update_status(self, text):
        self.root.after(0, lambda: self.lbl_status.config(text=text))

    def _cancel(self):
        self.draw_engine.cancel()

    def _show_about(self):
        AboutDialog(self.root)

    def _paste_from_clipboard(self):
        import subprocess
        import io

        img = None

        # Try PIL ImageGrab first (works if xclip or wl-paste is installed)
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
        except Exception:
            pass

        # Fallback: xclip
        if img is None:
            for mime in ["image/png", "image/bmp", "image/jpeg"]:
                try:
                    data = subprocess.check_output(
                        ["xclip", "-selection", "clipboard", "-t", mime, "-o"],
                        stderr=subprocess.DEVNULL)
                    img = Image.open(io.BytesIO(data))
                    break
                except Exception:
                    continue

        # Fallback: xsel
        if img is None:
            try:
                data = subprocess.check_output(
                    ["xsel", "--clipboard", "--output"],
                    stderr=subprocess.DEVNULL)
                img = Image.open(io.BytesIO(data))
            except Exception:
                pass

        # Fallback: wl-paste (Wayland)
        if img is None:
            try:
                data = subprocess.check_output(
                    ["wl-paste", "--type", "image/png"],
                    stderr=subprocess.DEVNULL)
                img = Image.open(io.BytesIO(data))
            except Exception:
                pass

        if img is None:
            self._update_status("No image in clipboard. Install xclip: sudo apt install xclip")
            return

        rgb = np.array(img.convert("RGB"))
        self.gray_image = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        self.image_path = "(clipboard)"
        self.lbl_file.config(text="(pasted from clipboard)")
        self._do_crop()

    def _populate_fonts(self):
        self._font_list = discover_fonts()
        families = sorted(set(f["family"] for f in self._font_list))
        self._font_combo["values"] = families
        if families:
            self._font_combo.current(0)
            self._on_font_change()

    def _browse_font(self):
        path = filedialog.askopenfilename(
            filetypes=[("Font files", "*.ttf *.otf"), ("All", "*.*")]
        )
        if path:
            self.font_path = path
            name = path.split("/")[-1].split("\\")[-1]
            self._font_combo.set(name)
            self._on_text_change()

    def _on_font_change(self):
        selected = self._font_combo.get()
        for f in self._font_list:
            if f["family"] == selected:
                self.font_path = f["path"]
                break
        self._on_text_change()

    def _on_text_change(self):
        text = self._text_box.get("1.0", "end-1c").strip()
        if not text or not self.font_path:
            return

        self.input_mode = "text"
        self._update_input_mode_visibility()

        max_w = None
        if self.contour_bounds:
            max_w = self.contour_bounds[0]

        try:
            self.contours = render_text(
                text, self.font_path, self.font_size.get(),
                max_width=max_w)
        except Exception as e:
            self._update_status(f"Text error: {e}")
            return

        if not self.contours:
            self._update_status("No glyphs rendered.")
            return

        all_pts = np.vstack(self.contours)
        mins = all_pts.min(axis=0)
        maxs = all_pts.max(axis=0)
        self.contour_bounds = (maxs[0] - mins[0], maxs[1] - mins[1])

        for i, c in enumerate(self.contours):
            self.contours[i] = c - mins

        total_points = sum(len(c) for c in self.contours)
        self.lbl_contours.config(text=f"Contours: {len(self.contours)}, Total points: {total_points}")
        self.lbl_crop.config(text=f"Text: {self.contour_bounds[0]:.0f}x{self.contour_bounds[1]:.0f}px")
        self._update_status(f"Text rendered: {len(self.contours)} contours, {total_points} points")

        if self.auto_preview.get():
            self._open_preview()

    def _pick_canvas(self):
        if not self.contours and self.cropped_image is None:
            self._update_status("Load an image or SVG first.")
            return
        CanvasPicker(self.root, self._apply_canvas_target)

    def _apply_canvas_target(self, x, y, width, height):
        self.offset_x.set(x)
        self.offset_y.set(y)
        self.relative_offset.set(False)
        if self.cropped_image is not None:
            img_h, img_w = self.cropped_image.shape[:2]
        elif self.contour_bounds:
            img_w, img_h = self.contour_bounds
        else:
            return
        scale_x = width / img_w
        scale_y = height / img_h
        self.scale.set(round(min(scale_x, scale_y), 3))
        self._update_status(f"Canvas set: {width}x{height} at ({x},{y}), scale={self.scale.get():.3f}")

    def _quit(self):
        self.config.update({
            "scale": self.scale.get(),
            "offset_x": self.offset_x.get(),
            "offset_y": self.offset_y.get(),
            "speed": self.speed.get(),
            "mouse_button": self.mouse_button.get(),
            "delay_before": self.delay_before.get(),
            "relative_offset": self.relative_offset.get(),
            "auto_preview": self.auto_preview.get(),
        })
        save_config(self.config)
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    Inkspire()

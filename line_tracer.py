#!/usr/bin/env python3
"""
Line Tracer – traces line art by moving the mouse along extracted contours.
Uses ctypes X11 calls for fast, jitter-free mouse control.

Supports: B/W line art, colored images, halftones via multiple detection modes.

Usage: sudo python3 line_tracer.py

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
from mouse_x11 import mouse_move, mouse_down, mouse_up, get_mouse_pos, is_escape_pressed
from detection import detect_art_bounds, detect_edges

MODES = ["Threshold", "Canny Edge", "Adaptive Threshold", "Auto"]

# ── Crop Dialog ──

class CropDialog:
    def __init__(self, parent, cv_gray_image, auto_rect=None):
        self.result = None
        self.orig_img = cv_gray_image
        self.oh, self.ow = cv_gray_image.shape

        self.win = tk.Toplevel(parent)
        self.win.title("Crop Image (drag to select, Enter to confirm)")
        self.win.grab_set()
        self.win.focus_force()

        max_w, max_h = 1100, 750
        self.display_scale = min(max_w / self.ow, max_h / self.oh, 1.0)
        self.dw = int(self.ow * self.display_scale)
        self.dh = int(self.oh * self.display_scale)

        info_frame = ttk.Frame(self.win)
        info_frame.pack(fill="x", padx=6, pady=3)
        self.lbl_info = ttk.Label(info_frame,
                                   text=f"Image: {self.ow}x{self.oh}px. Drag to crop or click 'Use Full Image'.")
        self.lbl_info.pack(side="left")

        self.canvas = tk.Canvas(self.win, width=self.dw, height=self.dh,
                                cursor="crosshair", bg="gray20")
        self.canvas.pack(padx=6, pady=3)

        rgb = cv2.cvtColor(cv_gray_image, cv2.COLOR_GRAY2RGB)
        pil = Image.fromarray(rgb).resize((self.dw, self.dh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(pil)
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img, tags="bg")

        self._rect = None
        self._start_x = 0
        self._start_y = 0

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(fill="x", padx=6, pady=6)
        ttk.Button(btn_frame, text="Confirm Crop", command=self._confirm).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Use Full Image", command=self._use_full).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side="right", padx=4)

        self.win.bind("<Return>", lambda e: self._confirm())
        self.win.bind("<Escape>", lambda e: self._cancel())

        if auto_rect is not None:
            ax, ay, aw, ah = auto_rect
            s = self.display_scale
            dx1, dy1 = int(ax * s), int(ay * s)
            dx2, dy2 = int((ax + aw) * s), int((ay + ah) * s)
            self._start_x = dx1
            self._start_y = dy1
            self._rect = self.canvas.create_rectangle(
                dx1, dy1, dx2, dy2, outline="#00ff00", width=2, dash=(4, 4))
            self.lbl_info.config(
                text=f"Auto-detected: ({ax},{ay}) {aw}x{ah}px. Adjust or Enter to confirm.")

        parent.wait_window(self.win)

    def _on_press(self, event):
        self._start_x = event.x
        self._start_y = event.y
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00ff00", width=2, dash=(4, 4))

    def _on_drag(self, event):
        if self._rect:
            self.canvas.coords(self._rect, self._start_x, self._start_y, event.x, event.y)
            x1, y1, x2, y2 = self._get_real_coords()
            self.lbl_info.config(text=f"Selection: ({x1},{y1}) to ({x2},{y2}) = {x2 - x1}x{y2 - y1}px")

    def _on_release(self, event):
        if self._rect:
            self.canvas.coords(self._rect, self._start_x, self._start_y, event.x, event.y)

    def _get_real_coords(self):
        if not self._rect:
            return 0, 0, self.ow, self.oh
        coords = self.canvas.coords(self._rect)
        if len(coords) < 4:
            return 0, 0, self.ow, self.oh
        dx1, dy1, dx2, dy2 = coords
        dx1, dx2 = min(dx1, dx2), max(dx1, dx2)
        dy1, dy2 = min(dy1, dy2), max(dy1, dy2)
        s = self.display_scale
        return (max(0, int(dx1 / s)), max(0, int(dy1 / s)),
                min(self.ow, int(dx2 / s)), min(self.oh, int(dy2 / s)))

    def _confirm(self):
        x1, y1, x2, y2 = self._get_real_coords()
        w, h = x2 - x1, y2 - y1
        self.result = (x1, y1, w, h) if w > 5 and h > 5 else None
        self.win.destroy()

    def _use_full(self):
        self.result = None
        self.win.destroy()

    def _cancel(self):
        self.result = "CANCEL"
        self.win.destroy()


# ── Main GUI ──

class LineTracer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Line Tracer")
        self.root.resizable(False, False)

        self.image_path = None
        self.gray_image = None
        self.cropped_image = None
        self.contours = []
        self.drawing = False
        self.cancelled = False
        self._preview_timer = None
        self._suggested = {}
        self._escape_was_pressed = False

        # (var_name, var, slider, entry, is_int, from_, to, step)
        self._widgets = []

        # Detection mode
        self.detect_mode = tk.StringVar(value="Auto")

        # Settings
        self.scale = tk.DoubleVar(value=1.00)
        self.offset_x = tk.IntVar(value=200)
        self.offset_y = tk.IntVar(value=200)
        self.speed = tk.DoubleVar(value=0.02)
        self.threshold = tk.IntVar(value=128)
        self.canny_lo = tk.IntVar(value=50)
        self.canny_hi = tk.IntVar(value=150)
        self.adaptive_block = tk.IntVar(value=11)
        self.adaptive_c = tk.IntVar(value=2)
        self.blur_radius = tk.IntVar(value=0)
        self.morph_iter = tk.IntVar(value=0)
        self.min_contour_len = tk.IntVar(value=10)
        self.simplify = tk.DoubleVar(value=1.0)
        self.mouse_button = tk.StringVar(value="right")
        self.delay_before = tk.IntVar(value=3)
        self.use_skeleton = tk.BooleanVar(value=False)
        self.relative_offset = tk.BooleanVar(value=True)
        self.auto_preview = tk.BooleanVar(value=True)

        self._preview_win = None
        self._preview_label = None

        self._build_gui()
        self._setup_traces()
        self._update_mode_visibility()
        self.root.mainloop()

    # ── Linked slider + entry + step buttons ──

    def _linked_slider_entry(self, parent, row, label, var, var_name,
                              from_, to, resolution, width=8, pad=None):
        if pad is None:
            pad = {"padx": 6, "pady": 3}

        is_int = isinstance(var, tk.IntVar)
        step = resolution

        lbl = ttk.Label(parent, text=label)
        lbl.grid(row=row, column=0, sticky="w", **pad)

        slider = tk.Scale(
            parent, from_=from_, to=to, resolution=resolution,
            orient="horizontal", showvalue=False,
            command=lambda val, v=var, ii=is_int, vn=var_name: self._slider_cmd(val, vn, v, ii)
        )
        slider.set(var.get())
        slider.grid(row=row, column=1, sticky="ew", **pad)

        right = ttk.Frame(parent)
        right.grid(row=row, column=2, sticky="w", **pad)

        btn_down = ttk.Button(right, text="\u25bc", width=2,
                              command=lambda: self._step_value(var_name, -step))
        btn_down.pack(side="left")

        entry = ttk.Entry(right, width=width)
        entry.pack(side="left", padx=2)
        entry.insert(0, str(var.get()))

        btn_up = ttk.Button(right, text="\u25b2", width=2,
                            command=lambda: self._step_value(var_name, step))
        btn_up.pack(side="left")

        entry.bind("<Return>", lambda ev, vn=var_name: self._entry_commit(vn))
        entry.bind("<FocusOut>", lambda ev, vn=var_name: self._entry_commit(vn))

        self._widgets.append((var_name, var, slider, entry, is_int, from_, to, step, lbl, right))
        return slider, entry

    def _slider_cmd(self, val, var_name, var, is_int):
        v = int(float(val)) if is_int else round(float(val), 3)
        var.set(v)
        for vn, vr, sl, ent, ii, f, t, st, lb, rt in self._widgets:
            if vn == var_name:
                ent.delete(0, tk.END)
                ent.insert(0, str(v))
                break

    def _entry_commit(self, var_name):
        for vn, var, slider, entry, is_int, from_, to, step, lb, rt in self._widgets:
            if vn == var_name:
                try:
                    raw = entry.get().strip()
                    v = int(raw) if is_int else round(float(raw), 3)
                    v = max(from_, min(to, v))
                except ValueError:
                    v = var.get()
                var.set(v)
                slider.set(v)
                entry.delete(0, tk.END)
                entry.insert(0, str(v))
                break

    def _step_value(self, var_name, delta):
        for vn, var, slider, entry, is_int, from_, to, step, lb, rt in self._widgets:
            if vn == var_name:
                cur = var.get()
                nv = int(cur + delta) if is_int else round(cur + delta, 3)
                nv = max(from_, min(to, nv))
                var.set(nv)
                slider.set(nv)
                entry.delete(0, tk.END)
                entry.insert(0, str(nv))
                break

    def _sync_all_widgets(self):
        for vn, var, slider, entry, is_int, f, t, st, lb, rt in self._widgets:
            v = var.get()
            slider.set(v)
            entry.delete(0, tk.END)
            entry.insert(0, str(v))

    def _set_widget_visible(self, var_name, visible):
        """Show/hide a slider row by var_name."""
        for vn, var, slider, entry, is_int, f, t, st, lbl, right in self._widgets:
            if vn == var_name:
                if visible:
                    lbl.grid()
                    slider.grid()
                    right.grid()
                else:
                    lbl.grid_remove()
                    slider.grid_remove()
                    right.grid_remove()
                break

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

    def _on_mode_change(self):
        self._update_mode_visibility()
        self._schedule_preview_update()

    def _schedule_preview_update(self):
        if not self.auto_preview.get() or self.cropped_image is None:
            return
        if self._preview_timer is not None:
            self.root.after_cancel(self._preview_timer)
        self._preview_timer = self.root.after(300, self._update_live_preview)

    def _update_live_preview(self):
        self._preview_timer = None
        self._extract_contours()
        if self._preview_win is not None and self._preview_win.winfo_exists():
            self._render_preview_in_window()

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

        # ── Detection Mode ──
        frame_mode = ttk.LabelFrame(self.root, text="Detection Mode")
        frame_mode.pack(fill="x", **pad)

        mode_row = ttk.Frame(frame_mode)
        mode_row.pack(fill="x", **pad)
        for m in MODES:
            ttk.Radiobutton(mode_row, text=m, variable=self.detect_mode, value=m).pack(side="left", padx=4)

        # ── Detection Parameters ──
        frame_det = ttk.LabelFrame(self.root, text="Detection Parameters")
        frame_det.pack(fill="x", **pad)

        row = 0
        self._linked_slider_entry(frame_det, row, "Threshold (1-254):",
                                   self.threshold, "threshold", 1, 254, 1, pad=pad)
        row += 1
        self._linked_slider_entry(frame_det, row, "Canny low:",
                                   self.canny_lo, "canny_lo", 1, 300, 1, pad=pad)
        row += 1
        self._linked_slider_entry(frame_det, row, "Canny high:",
                                   self.canny_hi, "canny_hi", 1, 500, 1, pad=pad)
        row += 1
        self._linked_slider_entry(frame_det, row, "Adaptive block size:",
                                   self.adaptive_block, "adaptive_block", 3, 99, 2, pad=pad)
        row += 1
        self._linked_slider_entry(frame_det, row, "Adaptive C:",
                                   self.adaptive_c, "adaptive_c", -20, 20, 1, pad=pad)

        frame_det.columnconfigure(1, weight=1)

        # ── Pre/Post Processing ──
        frame_proc = ttk.LabelFrame(self.root, text="Pre/Post Processing")
        frame_proc.pack(fill="x", **pad)

        row = 0
        self._linked_slider_entry(frame_proc, row, "Blur radius (halftone):",
                                   self.blur_radius, "blur_radius", 0, 20, 1, pad=pad)
        row += 1
        self._linked_slider_entry(frame_proc, row, "Morph cleanup (iter):",
                                   self.morph_iter, "morph_iter", 0, 10, 1, pad=pad)

        frame_proc.columnconfigure(1, weight=1)

        # ── Contour Settings ──
        frame_cont = ttk.LabelFrame(self.root, text="Contour Settings")
        frame_cont.pack(fill="x", **pad)

        row = 0
        self._linked_slider_entry(frame_cont, row, "Min contour length:",
                                   self.min_contour_len, "min_contour_len", 1, 500, 1, pad=pad)
        row += 1
        self._linked_slider_entry(frame_cont, row, "Simplify (epsilon):",
                                   self.simplify, "simplify", 0.1, 10.0, 0.1, pad=pad)
        row += 1
        ttk.Checkbutton(frame_cont, text="Skeletonize (thin lines to 1px)",
                        variable=self.use_skeleton).grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        row += 1
        self.btn_suggested = ttk.Button(frame_cont, text="Reset to Suggested",
                                        command=self._apply_suggested, state="disabled")
        self.btn_suggested.grid(row=row, column=0, columnspan=3, sticky="w", **pad)

        frame_cont.columnconfigure(1, weight=1)

        # ── Drawing Settings ──
        frame_draw = ttk.LabelFrame(self.root, text="Drawing Settings")
        frame_draw.pack(fill="x", **pad)

        row = 0
        self._linked_slider_entry(frame_draw, row, "Scale:",
                                   self.scale, "scale", 0.10, 10.0, 0.01, pad=pad)
        row += 1
        ttk.Label(frame_draw, text="Offset X (px):").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frame_draw, textvariable=self.offset_x, width=8).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frame_draw, text="Offset Y (px):").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frame_draw, textvariable=self.offset_y, width=8).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Checkbutton(frame_draw, text="Relative to mouse (bottom-left corner)",
                        variable=self.relative_offset).grid(row=row, column=0, columnspan=3, sticky="w", **pad)

        row += 1
        self._linked_slider_entry(frame_draw, row, "Speed (s/point):",
                                   self.speed, "speed", 0.0, 0.1, 0.001, pad=pad)

        row += 1
        ttk.Label(frame_draw, text="Mouse button:").grid(row=row, column=0, sticky="w", **pad)
        btn_frame = ttk.Frame(frame_draw)
        btn_frame.grid(row=row, column=1, sticky="w", **pad)
        ttk.Radiobutton(btn_frame, text="Left", variable=self.mouse_button, value="left").pack(side="left")
        ttk.Radiobutton(btn_frame, text="Right", variable=self.mouse_button, value="right").pack(side="left")

        row += 1
        ttk.Label(frame_draw, text="Delay before start (s):").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frame_draw, textvariable=self.delay_before, width=8).grid(row=row, column=1, sticky="w", **pad)

        frame_draw.columnconfigure(1, weight=1)

        # ── Status ──
        self.lbl_status = ttk.Label(self.root, text="Load an image to begin.")
        self.lbl_status.pack(**pad)
        self.lbl_contours = ttk.Label(self.root, text="")
        self.lbl_contours.pack(**pad)
        self.lbl_crop = ttk.Label(self.root, text="")
        self.lbl_crop.pack(**pad)

        # ── Buttons ──
        frame_btn = ttk.Frame(self.root)
        frame_btn.pack(fill="x", **pad)
        ttk.Button(frame_btn, text="Preview", command=self._open_preview).pack(side="left", **pad)
        ttk.Checkbutton(frame_btn, text="Live", variable=self.auto_preview).pack(side="left", **pad)
        ttk.Button(frame_btn, text="Start Drawing", command=self._start_drawing).pack(side="left", **pad)
        ttk.Button(frame_btn, text="Quit", command=self._quit).pack(side="right", **pad)

    # ── Image Loading, Crop, Auto-propose ──

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"), ("All", "*.*")]
        )
        if path:
            self.image_path = path
            self.gray_image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if self.gray_image is None:
                self.lbl_status.config(text="Error: could not read image.")
                return
            self.lbl_file.config(text=path.split("/")[-1])
            self._do_crop()

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

        self._compute_suggested()
        self._apply_suggested()
        self._extract_contours()
        if self.auto_preview.get():
            self._open_preview()

    def _compute_suggested(self):
        img = self.cropped_image
        if img is None:
            return
        h, w = img.shape

        # Otsu threshold
        otsu_val, binary_otsu = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        otsu_val = max(1, min(254, int(otsu_val)))

        ink_ratio = cv2.countNonZero(binary_otsu) / (h * w)

        # Diagonal-based min contour length
        diag = np.sqrt(h * h + w * w)
        proposed_min = max(5, min(100, int(diag * 0.01)))

        # Simplify based on ink density
        if ink_ratio > 0.15:
            proposed_eps = 2.0
        elif ink_ratio > 0.05:
            proposed_eps = 1.0
        else:
            proposed_eps = 0.5

        # Detect image type for mode suggestion
        mean, stddev = cv2.meanStdDev(img)
        std = stddev[0][0]
        lap_var = cv2.Laplacian(img, cv2.CV_64F).var()

        if lap_var > 500 and std > 40:
            proposed_mode = "Canny Edge"
            proposed_blur = max(1, min(5, int(np.sqrt(lap_var) / 50)))
            proposed_morph = 1
            proposed_canny_lo = max(10, int(otsu_val * 0.3))
            proposed_canny_hi = max(proposed_canny_lo + 20, int(otsu_val * 0.9))
        elif std > 60 and 0.2 < ink_ratio < 0.8:
            proposed_mode = "Adaptive Threshold"
            proposed_blur = 1
            proposed_morph = 1
            proposed_canny_lo = 50
            proposed_canny_hi = 150
        else:
            proposed_mode = "Threshold"
            proposed_blur = 0
            proposed_morph = 0
            proposed_canny_lo = 50
            proposed_canny_hi = 150

        self._suggested = {
            "threshold": otsu_val,
            "min_contour_len": proposed_min,
            "simplify": proposed_eps,
            "detect_mode": proposed_mode,
            "blur_radius": proposed_blur,
            "morph_iter": proposed_morph,
            "canny_lo": proposed_canny_lo,
            "canny_hi": proposed_canny_hi,
            "adaptive_block": 11,
            "adaptive_c": 2,
            "ink_ratio": ink_ratio,
            "lap_var": lap_var,
            "std": std,
        }
        self.btn_suggested.config(state="normal")

    def _apply_suggested(self):
        if not self._suggested:
            return
        s = self._suggested

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

        edges = detect_edges(
            self.cropped_image,
            mode=self.detect_mode.get(),
            threshold=self.threshold.get(),
            canny_lo=self.canny_lo.get(),
            canny_hi=self.canny_hi.get(),
            adaptive_block=self.adaptive_block.get(),
            adaptive_c=self.adaptive_c.get(),
            blur_radius=self.blur_radius.get(),
            morph_iterations=self.morph_iter.get(),
        )

        if self.use_skeleton.get():
            edges = self._skeletonize(edges)

        contours_raw, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        min_len = self.min_contour_len.get()
        eps = self.simplify.get()

        self.contours = []
        for c in contours_raw:
            if len(c) < min_len:
                continue
            if eps > 0:
                approx = cv2.approxPolyDP(c, eps, closed=False)
            else:
                approx = c
            self.contours.append(approx.reshape(-1, 2))

        total_points = sum(len(c) for c in self.contours)
        self.lbl_contours.config(text=f"Contours: {len(self.contours)}, Total points: {total_points}")

    def _skeletonize(self, binary):
        skel = np.zeros_like(binary)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        temp = binary.copy()
        while True:
            eroded = cv2.erode(temp, element)
            opened = cv2.dilate(eroded, element)
            subset = cv2.subtract(temp, opened)
            skel = cv2.bitwise_or(skel, subset)
            temp = eroded.copy()
            if cv2.countNonZero(temp) == 0:
                break
        return skel

    # ── Preview ──

    def _open_preview(self):
        self._extract_contours()
        if not self.contours:
            self.lbl_status.config(text="No contours found. Adjust parameters.")
            return
        if self._preview_win is None or not self._preview_win.winfo_exists():
            self._preview_win = tk.Toplevel(self.root)
            self._preview_win.title("Contour Preview (live)")
            self._preview_label = tk.Label(self._preview_win)
            self._preview_label.pack()
        self._render_preview_in_window()

    def _render_preview_in_window(self):
        if self.cropped_image is None:
            return
        if self._preview_win is None or not self._preview_win.winfo_exists():
            return

        h, w = self.cropped_image.shape
        s = self.scale.get()
        bpad = 10
        cw = int(w * s) + bpad * 2
        ch = int(h * s) + bpad * 2
        canvas = np.ones((ch, cw, 3), dtype=np.uint8) * 255

        for contour in self.contours:
            pts = (contour * s).astype(np.int32) + bpad
            for i in range(len(pts) - 1):
                p1 = tuple(np.clip(pts[i], 0, [cw - 1, ch - 1]))
                p2 = tuple(np.clip(pts[i + 1], 0, [cw - 1, ch - 1]))
                cv2.line(canvas, p1, p2, (0, 0, 0), 1)

        cv2.rectangle(canvas, (bpad, bpad), (bpad + int(w * s), bpad + int(h * s)), (200, 200, 200), 1)

        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        max_w, max_h = 1000, 700
        iw, ih = pil_img.size
        if iw > max_w or ih > max_h:
            ratio = min(max_w / iw, max_h / ih)
            pil_img = pil_img.resize((int(iw * ratio), int(ih * ratio)), Image.LANCZOS)

        tk_img = ImageTk.PhotoImage(pil_img)
        self._preview_label.config(image=tk_img)
        self._preview_label.image = tk_img

    # ── Drawing ──

    def _start_drawing(self):
        if not self.contours:
            self._extract_contours()
        if not self.contours:
            self.lbl_status.config(text="No contours to draw.")
            return
        self.cancelled = False
        self.drawing = True
        threading.Thread(target=self._draw_thread, daemon=True).start()

    def _draw_thread(self):
        delay = self.delay_before.get()
        for i in range(delay, 0, -1):
            if self._should_cancel():
                self._update_status("Cancelled.")
                self.drawing = False
                return
            self._update_status(f"Starting in {i}... switch to your canvas! (Esc to cancel)")
            if not self._sleep_with_cancel(1.0):
                self._update_status("Cancelled.")
                self.drawing = False
                return

        s = self.scale.get()
        spd = self.speed.get()
        btn = 1 if self.mouse_button.get() == "left" else 3

        if self.relative_offset.get():
            mx, my = get_mouse_pos()
            max_y = max(c[:, 1].max() for c in self.contours)
            ox, oy = mx, my - int(max_y * s)
        else:
            ox, oy = self.offset_x.get(), self.offset_y.get()

        total = len(self.contours)
        for idx, contour in enumerate(self.contours):
            if self._should_cancel():
                break
            self._update_status(f"Drawing contour {idx + 1}/{total}...")

            pts = contour.astype(np.float64) * s
            pts[:, 0] += ox
            pts[:, 1] += oy

            mouse_move(pts[0][0], pts[0][1])
            if not self._sleep_with_cancel(0.01):
                break

            mouse_down(btn)
            for pt in pts[1:]:
                if self._should_cancel():
                    mouse_up(btn)
                    break
                mouse_move(pt[0], pt[1])
                if spd > 0 and not self._sleep_with_cancel(spd):
                    mouse_up(btn)
                    break
            mouse_up(btn)
            if self.cancelled:
                break
            if not self._sleep_with_cancel(0.01):
                break

        if not self.cancelled:
            self._update_status("Drawing complete!")
        else:
            self._update_status("Drawing cancelled.")
        self.drawing = False

    def _update_status(self, text):
        self.root.after(0, lambda: self.lbl_status.config(text=text))

    def _should_cancel(self):
        if self.cancelled:
            return True
        esc_pressed = is_escape_pressed()
        if esc_pressed and not self._escape_was_pressed:
            self.cancelled = True
        self._escape_was_pressed = esc_pressed
        return self.cancelled

    def _sleep_with_cancel(self, duration, interval=0.02):
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            if self._should_cancel():
                return False
            time.sleep(min(interval, end_time - time.monotonic()))
        return not self._should_cancel()

    def _cancel(self):
        self.cancelled = True

    def _quit(self):
        self.cancelled = True
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    LineTracer()

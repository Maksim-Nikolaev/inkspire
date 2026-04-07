"""Interactive crop dialog for selecting the region of interest from a loaded image."""

import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk


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

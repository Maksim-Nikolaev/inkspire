"""Interactive crop dialog for selecting the region of interest from a loaded image."""

import tkinter as tk

import cv2
from PIL import Image, ImageTk

from ui import theme
from ui.dialog import Dialog
from ui.theme import ctk
from ui.widgets import Pill, button

__all__ = ["CropDialog"]


class CropDialog:
    def __init__(self, parent, cv_gray_image, auto_rect=None):
        self.result = None
        self.oh, self.ow = cv_gray_image.shape

        self.win = Dialog(parent, "Crop image", resizable=False)
        self.win.columnconfigure(0, weight=1)

        max_w = min(1100, self.win.winfo_screenwidth() - 160)
        max_h = min(720, self.win.winfo_screenheight() - 260)
        self.display_scale = min(max_w / self.ow, max_h / self.oh, 1.0)
        self.dw = max(1, int(self.ow * self.display_scale))
        self.dh = max(1, int(self.oh * self.display_scale))

        header = ctk.CTkFrame(self.win, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 10))
        header.columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Crop image", font=theme.font(16, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header, text="Drag to select the part to trace. Enter confirms, Esc cancels.",
            text_color=theme.MUTED, anchor="w",
        ).grid(row=1, column=0, sticky="w")
        self.info = Pill(header, f"{self.ow} × {self.oh} px")
        self.info.grid(row=0, column=1, rowspan=2, sticky="e")

        frame = ctk.CTkFrame(self.win, fg_color=theme.SURFACE_2, border_width=1, border_color=theme.BORDER, corner_radius=theme.RADIUS)
        frame.grid(row=1, column=0, padx=20)
        self.canvas = tk.Canvas(frame, width=self.dw, height=self.dh, cursor="crosshair", highlightthickness=0, borderwidth=0, background=theme.pick(theme.SURFACE_2))
        self.canvas.pack(padx=8, pady=8)

        rgb = cv2.cvtColor(cv_gray_image, cv2.COLOR_GRAY2RGB)
        self._base = Image.fromarray(rgb).resize((self.dw, self.dh), Image.LANCZOS)
        self._dimmed = Image.blend(self._base, Image.new("RGB", self._base.size, (8, 10, 18)), 0.55)
        self._tk_img = ImageTk.PhotoImage(self._base, master=self.canvas)
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        self._rect = None
        self._start_x = 0
        self._start_y = 0
        self._paint_job = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        footer = ctk.CTkFrame(self.win, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(14, 18))
        footer.columnconfigure(1, weight=1)
        button(footer, "Use full image", self._use_full).grid(row=0, column=0, sticky="w")
        button(footer, "Cancel", self._cancel, kind="ghost", width=90).grid(row=0, column=2, padx=(0, 8))
        button(footer, "Crop", self._confirm, kind="primary", width=110).grid(row=0, column=3)

        self.win.bind("<Return>", lambda e: self._confirm())
        self.win.bind("<KP_Enter>", lambda e: self._confirm())
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

        if auto_rect is not None:
            ax, ay, aw, ah = auto_rect
            s = self.display_scale
            self._start_x, self._start_y = int(ax * s), int(ay * s)
            self._set_rect(self._start_x, self._start_y, int((ax + aw) * s), int((ay + ah) * s))
            self.info.set(f"Auto-detected {aw} × {ah} px", "accent")

        self.win.present()
        parent.wait_window(self.win)

    def _set_rect(self, x1, y1, x2, y2):
        x1, x2 = sorted((max(0, min(self.dw, x1)), max(0, min(self.dw, x2))))
        y1, y2 = sorted((max(0, min(self.dh, y1)), max(0, min(self.dh, y2))))

        if self._rect is None:
            self._rect = self.canvas.create_rectangle(x1, y1, x2, y2, outline=theme.pick(theme.ACCENT), width=2)
        else:
            self.canvas.coords(self._rect, x1, y1, x2, y2)

        if not self._paint_job:
            self._paint_job = self.canvas.after_idle(self._paint)

    def _paint(self):
        self._paint_job = None
        x1, y1, x2, y2 = (int(v) for v in self.canvas.coords(self._rect))

        if x2 - x1 < 2 or y2 - y1 < 2:
            self._tk_img.paste(self._base)
            return

        frame = self._dimmed.copy()
        frame.paste(self._base.crop((x1, y1, x2, y2)), (x1, y1))
        self._tk_img.paste(frame)

    def _on_press(self, event):
        self._start_x = event.x
        self._start_y = event.y
        self._set_rect(event.x, event.y, event.x, event.y)

    def _on_drag(self, event):
        self._set_rect(self._start_x, self._start_y, event.x, event.y)
        x1, y1, x2, y2 = self._get_real_coords()
        self.info.set(f"{x2 - x1} × {y2 - y1} px", "accent")

    def _on_release(self, event):
        self._set_rect(self._start_x, self._start_y, event.x, event.y)

    def _get_real_coords(self):
        if not self._rect:
            return 0, 0, self.ow, self.oh

        dx1, dy1, dx2, dy2 = self.canvas.coords(self._rect)
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

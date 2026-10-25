"""Contour preview: a canvas that fits the drawing onto a sheet, docked or in its own window."""

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

from ui import theme
from ui.theme import ctk

__all__ = ["render_preview", "PreviewCanvas", "PreviewWindow"]

_PAD = 28


def _rgb(hex_color):
    hex_color = hex_color.lstrip("#")

    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def render_preview(contours, scale, image_shape, box_w, box_h, palette=None):
    """Draw contours, scaled like the real drawing, onto a sheet fitted into a box_w x box_h image."""
    background, sheet, border, ink = palette or (
        theme.pick(theme.SURFACE_2), theme.pick(theme.SURFACE), theme.pick(theme.BORDER_STRONG), theme.pick(theme.TEXT),
    )
    h, w = image_shape
    draw_w = max(1.0, w * scale)
    draw_h = max(1.0, h * scale)
    fit = max(0.01, min((box_w - 2 * _PAD) / draw_w, (box_h - 2 * _PAD) / draw_h))
    sheet_w = max(1, int(draw_w * fit))
    sheet_h = max(1, int(draw_h * fit))
    x0 = (box_w - sheet_w) // 2
    y0 = (box_h - sheet_h) // 2

    canvas = np.empty((box_h, box_w, 3), dtype=np.uint8)
    canvas[:] = _rgb(background)
    cv2.rectangle(canvas, (x0 - 1, y0 - 1), (x0 + sheet_w, y0 + sheet_h), _rgb(border), 1)
    canvas[y0:y0 + sheet_h, x0:x0 + sheet_w] = _rgb(sheet)

    # cv2 draws with 4 fractional bits, so points are pre-multiplied by 16.
    factor = scale * fit * 16
    offset = np.array([x0 * 16, y0 * 16])
    polylines = [(np.asarray(c, dtype=np.float64) * factor + offset).round().astype(np.int32).reshape(-1, 1, 2) for c in contours if len(c) > 1]
    thickness = 2 if fit * scale >= 2.5 else 1
    cv2.polylines(canvas, polylines, False, _rgb(ink), thickness, cv2.LINE_AA, shift=4)

    return Image.fromarray(canvas)


class PreviewCanvas:
    """A Tk canvas showing the latest contours fitted to its size, or an empty-state message."""

    def __init__(self, parent, empty_title="", empty_hint=""):
        self.canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        self.canvas.bind("<Configure>", lambda e: self._schedule_redraw())

        self._data = None
        self._photo = None
        self._redraw_job = None
        self._empty_title = empty_title
        self._empty_hint = empty_hint
        self._empty_widgets = []

    def set_empty(self, title, hint, actions=()):
        """Text and buttons shown while there is nothing to preview."""
        self._empty_title = title
        self._empty_hint = hint
        self._empty_widgets = list(actions)

        if self._data is None:
            self._redraw()

    def show(self, contours, scale, image_shape):
        self._data = (contours, scale, image_shape)
        self._redraw()

    def clear(self):
        self._data = None
        self._redraw()

    def refresh_theme(self):
        self._redraw()

    def _schedule_redraw(self):
        if self._redraw_job:
            self.canvas.after_cancel(self._redraw_job)

        self._redraw_job = self.canvas.after(60, self._redraw)

    def _redraw(self):
        self._redraw_job = None

        if not self.canvas.winfo_exists():
            return

        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        self.canvas.configure(background=theme.pick(theme.SURFACE_2))
        self.canvas.delete("all")

        if self._data is None or not self._data[0]:
            self._draw_empty(w, h)
            return

        contours, scale, image_shape = self._data
        self._photo = ImageTk.PhotoImage(render_preview(contours, scale, image_shape, w, h), master=self.canvas)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

    def _draw_empty(self, w, h):
        cx, cy = w // 2, h // 2 - 24

        self.canvas.create_text(cx, cy, text=self._empty_title, fill=theme.pick(theme.TEXT), font=theme.font(15, "bold"))
        self.canvas.create_text(cx, cy + 26, text=self._empty_hint, fill=theme.pick(theme.MUTED), font=theme.font(13), width=max(200, w - 80), justify="center")

        if self._empty_widgets:
            gap = 8
            widths = [widget.winfo_reqwidth() for widget in self._empty_widgets]
            x = cx - (sum(widths) + gap * (len(widths) - 1)) // 2

            for widget, width in zip(self._empty_widgets, widths):
                self.canvas.create_window(x, cy + 70, window=widget, anchor="w")
                x += width + gap


class PreviewWindow:
    """The preview in a separate, resizable window."""

    def __init__(self, parent):
        self._win = ctk.CTkToplevel(parent)
        self._win.title("Inkspire preview")
        self._win.geometry("900x700")
        self._win.minsize(320, 240)
        theme.apply_window_icon(self._win)

        self._preview = PreviewCanvas(self._win, empty_title="Nothing to preview", empty_hint="Load an image, an SVG or some text first.")
        self._preview.canvas.pack(fill="both", expand=True)

    def is_open(self) -> bool:
        try:
            return bool(self._win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        self._win.lift()
        self._win.focus_force()

    def close(self):
        self._win.destroy()

    def refresh_theme(self):
        self._preview.refresh_theme()

    def render(self, contours, scale, image_shape):
        self._preview.show(contours, scale, image_shape)

"""Screen region picker for defining the drawing canvas target."""

import sys
import tkinter as tk

from PIL import Image, ImageTk

from ui import theme

__all__ = ["CanvasPicker"]

_HINT = "Drag over the area to draw in  ·  Esc or right-click cancels"


class CanvasPicker:
    def __init__(self, parent, on_complete):
        self.on_complete = on_complete
        self.first_click = None

        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        screenshot = self._grab(screen_w, screen_h)

        self.overlay = tk.Toplevel(parent)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{screen_w}x{screen_h}+0+0")
        self.overlay.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.overlay, highlightthickness=0, width=screen_w, height=screen_h,
                                cursor="crosshair", background="#000000")
        self.canvas.pack()

        if screenshot is not None:
            self._base = screenshot
            self._dimmed = Image.blend(screenshot, Image.new("RGB", screenshot.size, (8, 10, 18)), 0.5)
            self._bg_img = ImageTk.PhotoImage(self._dimmed, master=self.canvas)
            self.canvas.create_image(0, 0, anchor="nw", image=self._bg_img)
            self._spot_img = None
            self._spot = self.canvas.create_image(0, 0, anchor="nw")
        else:
            # No screenshot (e.g. Wayland): fall back to a see-through tint where the window manager allows it.
            self._base = None

            try:
                self.overlay.attributes("-alpha", 0.45)
            except tk.TclError:
                pass

        accent = theme.pick(theme.ACCENT)
        self._rect = self.canvas.create_rectangle(0, 0, 0, 0, outline=accent, width=2, state="hidden")
        self._size_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill=accent, outline="", state="hidden")
        self._size_text = self.canvas.create_text(0, 0, text="", fill=theme.pick(theme.ON_ACCENT), font=theme.font(12, "bold"), anchor="nw", state="hidden")

        hint_font = theme.font(14)
        hint = self.canvas.create_text(screen_w // 2, 56, text=_HINT, fill="#ffffff", font=hint_font)
        x1, y1, x2, y2 = self.canvas.bbox(hint)
        pill = self.canvas.create_rectangle(x1 - 18, y1 - 10, x2 + 18, y2 + 10, fill="#141821", outline="#353d4e")
        self.canvas.tag_raise(hint, pill)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", lambda e: self._cancel())
        self.canvas.bind("<ButtonPress-2>", lambda e: self._cancel())
        self.canvas.bind("<ButtonPress-3>", lambda e: self._cancel())
        self.overlay.focus_force()
        self.overlay.after(50, self._grab_input)

    @staticmethod
    def _grab(screen_w, screen_h):
        # On macOS a screenshot needs the Screen Recording permission; the see-through overlay avoids that prompt.
        if sys.platform == "darwin":
            return None

        try:
            from PIL import ImageGrab

            shot = ImageGrab.grab(bbox=(0, 0, screen_w, screen_h)).convert("RGB")
        except Exception:
            return None

        if shot.size != (screen_w, screen_h):
            shot = shot.resize((screen_w, screen_h), Image.LANCZOS)

        return None if shot.getbbox() is None else shot

    def _grab_input(self):
        try:
            self.overlay.grab_set()
            self.overlay.focus_force()
        except tk.TclError:
            pass

    def _on_press(self, event):
        self.first_click = (event.x_root, event.y_root)

    def _on_drag(self, event):
        if not self.first_click or not self.canvas.winfo_exists():
            return

        x1, y1 = self.first_click
        left, top = min(x1, event.x_root), min(y1, event.y_root)
        right, bottom = max(x1, event.x_root), max(y1, event.y_root)

        self.canvas.coords(self._rect, left, top, right, bottom)
        self.canvas.itemconfigure(self._rect, state="normal")

        if self._base is not None and right - left > 1 and bottom - top > 1:
            self._spot_img = ImageTk.PhotoImage(self._base.crop((left, top, right, bottom)), master=self.canvas)
            self.canvas.itemconfigure(self._spot, image=self._spot_img)
            self.canvas.coords(self._spot, left, top)
            self.canvas.tag_raise(self._rect)

        self.canvas.itemconfigure(self._size_text, text=f"{right - left} × {bottom - top}", state="normal")
        self.canvas.coords(self._size_text, left + 8, bottom + 10)
        tx1, ty1, tx2, ty2 = self.canvas.bbox(self._size_text)
        self.canvas.coords(self._size_bg, tx1 - 6, ty1 - 3, tx2 + 6, ty2 + 3)
        self.canvas.itemconfigure(self._size_bg, state="normal")
        self.canvas.tag_raise(self._size_bg)
        self.canvas.tag_raise(self._size_text)

    def _on_release(self, event):
        if self.first_click is None:
            return

        x1, y1 = self.first_click
        x2, y2 = event.x_root, event.y_root
        self.overlay.destroy()

        left, top = min(x1, x2), min(y1, y2)
        width, height = abs(x2 - x1), abs(y2 - y1)

        if width > 0 and height > 0:
            self.on_complete(left, top, width, height)

    def _cancel(self):
        self.overlay.destroy()

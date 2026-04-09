"""Screen region picker for defining the drawing canvas target."""

import tkinter as tk
from PIL import Image, ImageTk

__all__ = ["CanvasPicker"]


class CanvasPicker:
    def __init__(self, parent, on_complete):
        self.on_complete = on_complete
        self.first_click = None

        # Capture a screenshot to use as the overlay background
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(bbox=(0, 0, screen_w, screen_h))
        except Exception:
            screenshot = Image.new("RGB", (screen_w, screen_h), "black")

        self.overlay = tk.Toplevel(parent)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{screen_w}x{screen_h}+0+0")
        self.overlay.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.overlay, highlightthickness=0,
                                width=screen_w, height=screen_h, cursor="crosshair")
        self.canvas.pack()

        self._bg_img = ImageTk.PhotoImage(screenshot)
        self.canvas.create_image(0, 0, anchor="nw", image=self._bg_img)

        # Semi-transparent dark tint over the screenshot
        self._tint = self.canvas.create_rectangle(
            0, 0, screen_w, screen_h, fill="black", stipple="gray25")

        self.label = self.canvas.create_text(
            screen_w // 2, 60,
            text="Drag to select your canvas area (Esc to cancel)",
            fill="white", font=("", 14))

        self._rect = None
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.overlay.bind("<Escape>", lambda e: self._cancel())
        self.overlay.focus_force()

    def _on_press(self, event):
        self.first_click = (event.x_root, event.y_root)

    def _on_drag(self, event):
        if self.first_click and self.canvas.winfo_exists():
            if self._rect:
                self.canvas.delete(self._rect)
            x1, y1 = self.first_click
            self._rect = self.canvas.create_rectangle(
                x1, y1, event.x_root, event.y_root,
                outline="lime", width=2, dash=(4, 4))

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

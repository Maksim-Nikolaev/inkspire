"""Screen region picker for defining the drawing canvas target."""

import tkinter as tk

__all__ = ["CanvasPicker"]


class CanvasPicker:
    def __init__(self, parent, on_complete):
        self.on_complete = on_complete
        self.first_click = None

        self.overlay = tk.Toplevel(parent)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-alpha", 0.3)
        self.overlay.configure(bg="black")
        self.overlay.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.overlay, highlightthickness=0,
                                bg="black", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self.label = tk.Label(
            self.overlay, text="Click the TOP-LEFT corner of your canvas",
            fg="white", bg="black", font=("", 14))
        self.label.place(relx=0.5, rely=0.1, anchor="center")

        self._rect = None
        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.overlay.bind("<Escape>", lambda e: self._cancel())

    def _on_click(self, event):
        if self.first_click is None:
            self.first_click = (event.x_root, event.y_root)
            self.label.config(text="Click the BOTTOM-RIGHT corner of your canvas")
        else:
            x1, y1 = self.first_click
            x2, y2 = event.x_root, event.y_root
            self.overlay.destroy()
            left, top = min(x1, x2), min(y1, y2)
            width, height = abs(x2 - x1), abs(y2 - y1)
            if width > 0 and height > 0:
                self.on_complete(left, top, width, height)

    def _on_motion(self, event):
        if self.first_click and self.canvas.winfo_exists():
            if self._rect:
                self.canvas.delete(self._rect)
            x1, y1 = self.first_click
            self._rect = self.canvas.create_rectangle(
                x1, y1, event.x_root, event.y_root,
                outline="lime", width=2, dash=(4, 4))

    def _cancel(self):
        self.overlay.destroy()

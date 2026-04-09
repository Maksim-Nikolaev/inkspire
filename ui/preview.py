"""Live contour preview window."""

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

__all__ = ["PreviewWindow"]


class PreviewWindow:
    def __init__(self, parent):
        self._win = tk.Toplevel(parent)
        self._win.title("Contour Preview (live)")
        self._label = tk.Label(self._win)
        self._label.pack()

    def is_open(self) -> bool:
        return self._win.winfo_exists()

    def focus(self):
        self._win.lift()
        self._win.focus_force()

    def close(self):
        self._win.destroy()

    def render(self, contours, scale, image_shape):
        h, w = image_shape
        s = scale
        bpad = 10
        cw = int(w * s) + bpad * 2
        ch = int(h * s) + bpad * 2
        canvas = np.ones((ch, cw, 3), dtype=np.uint8) * 255

        for contour in contours:
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
        self._label.config(image=tk_img)
        self._label.image = tk_img

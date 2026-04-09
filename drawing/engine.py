"""Drawing engine: replays contours as mouse movements with cancel/interrupt support."""

import time
import numpy as np
from drawing.mouse_x11 import mouse_move, mouse_down, mouse_up, get_mouse_pos, is_escape_pressed

__all__ = ["DrawEngine"]


class DrawEngine:
    def __init__(self, on_status, cancel_check=None):
        self.on_status = on_status
        self.cancel_flag = False
        self._cancel_check = cancel_check or is_escape_pressed
        self._was_pressed = False

    def run(self, contours, params):
        self.cancel_flag = False
        self._was_pressed = False

        delay = params["delay_before_start"]
        for i in range(delay, 0, -1):
            if self._should_cancel():
                self.on_status("Cancelled.")
                return
            self.on_status(f"Starting in {i}... switch to your canvas! (Esc to cancel)")
            if not self._sleep_with_cancel(1.0):
                self.on_status("Cancelled.")
                return

        s = params["scale"]
        spd = params["speed"]
        btn = 1 if params["mouse_button"] == "left" else 3

        if params["relative_to_mouse"]:
            mx, my = get_mouse_pos()
            max_y = max(c[:, 1].max() for c in contours)
            ox, oy = mx, my - int(max_y * s)
        else:
            ox, oy = params["offset_x"], params["offset_y"]

        total = len(contours)
        for idx, contour in enumerate(contours):
            if self._should_cancel():
                break
            self.on_status(f"Drawing contour {idx + 1}/{total}...")

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
            if self.cancel_flag:
                break
            if not self._sleep_with_cancel(0.01):
                break

        if not self.cancel_flag:
            self.on_status("Drawing complete!")
        else:
            self.on_status("Drawing cancelled.")

    def cancel(self):
        self.cancel_flag = True

    def _should_cancel(self):
        if self.cancel_flag:
            return True
        pressed = self._cancel_check()
        if pressed and not self._was_pressed:
            self.cancel_flag = True
        self._was_pressed = pressed
        return self.cancel_flag

    def _sleep_with_cancel(self, duration, interval=0.02):
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            if self._should_cancel():
                return False
            time.sleep(min(interval, end_time - time.monotonic()))
        return not self._should_cancel()

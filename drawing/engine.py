"""Drawing engine: replays contours as mouse movements with cancel/interrupt support."""

import time
import threading
import numpy as np
from drawing.mouse import mouse_move, mouse_down, mouse_up, get_mouse_pos

__all__ = ["DrawEngine"]


class DrawEngine:
    def __init__(self, on_status, cancel_check=None, on_progress=None):
        self.on_status = on_status
        self.on_progress = on_progress or (lambda done, total: None)
        self.cancel_flag = False

        if cancel_check is None:
            from core.keybinds import resolve_keycode, is_key_pressed

            esc_code = resolve_keycode("Escape")
            cancel_check = (lambda: is_key_pressed(esc_code)) if esc_code is not None else (lambda: False)

        self._cancel_check = cancel_check
        self._was_pressed = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._paused = False
        self._drawing = False

    @property
    def state(self):
        if not self._drawing:
            return "idle"
        if self._paused:
            return "paused"
        return "drawing"

    def pause(self):
        if self._drawing and not self._paused:
            self._paused = True
            self._pause_event.clear()

    def resume(self):
        if self._drawing and self._paused:
            self._paused = False
            self._pause_event.set()

    def run(self, contours, params):
        self.cancel_flag = False
        self._was_pressed = False
        self._paused = False
        self._pause_event.set()
        self._drawing = True

        try:
            self._run_inner(contours, params)
        finally:
            self._drawing = False
            self._paused = False
            self._pause_event.set()

    def _run_inner(self, contours, params):
        pts_per_sec = params["speed"]
        total_pts = sum(len(c) for c in contours)
        start_key = params.get("start_key_label", "F5")
        stop_key = params.get("stop_key_label", "Esc")

        if pts_per_sec > 0:
            eta_sec = total_pts / pts_per_sec

            if eta_sec >= 60:
                eta_str = f"~{int(eta_sec // 60)}m {int(eta_sec % 60)}s"
            else:
                eta_str = f"~{int(eta_sec)}s"

            eta_msg = f" (ETA {eta_str})"
        else:
            eta_msg = ""

        self.on_progress(0, total_pts)

        countdown = params["delay_before_start"]

        for i in range(countdown, 0, -1):
            if self._should_cancel():
                self.on_status("Cancelled.")
                return

            self.on_status(f"Starting in {i}{eta_msg}. Switch to your canvas, {stop_key} cancels.")

            if not self._sleep_with_cancel(1.0):
                self.on_status("Cancelled.")
                return

        s = params["scale"]
        delay = (1.0 / pts_per_sec) if pts_per_sec > 0 else 0
        btn = 1 if params["mouse_button"] == "left" else 3

        if params["relative_to_mouse"]:
            mx, my = get_mouse_pos()
            max_y = max(c[:, 1].max() for c in contours)
            ox, oy = mx, my - int(max_y * s)
        else:
            ox, oy = params["offset_x"], params["offset_y"]

        total = len(contours)
        done_pts = 0

        for idx, contour in enumerate(contours):
            if self._should_cancel():
                break

            self.on_status(f"Drawing contour {idx + 1}/{total}")

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

                if delay > 0 and not self._sleep_with_cancel(delay):
                    mouse_up(btn)
                    break

            mouse_up(btn)
            done_pts += len(contour)
            self.on_progress(done_pts, total_pts)

            if self.cancel_flag:
                break

            if not self._wait_if_paused(idx, total, start_key, stop_key):
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

    def _wait_if_paused(self, idx, total, start_key, stop_key):
        if not self._pause_event.is_set():
            self.on_status(f"Paused at contour {idx + 1}/{total}. {start_key} resumes, {stop_key} cancels.")

        while not self._pause_event.is_set():
            if self._should_cancel():
                return False

            self._pause_event.wait(timeout=0.05)

        return not self._should_cancel()

    def _sleep_with_cancel(self, duration, interval=0.02):
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            if self._should_cancel():
                return False
            time.sleep(min(interval, end_time - time.monotonic()))
        return not self._should_cancel()

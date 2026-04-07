"""Reusable compound widgets (linked slider + entry + step buttons)."""

import tkinter as tk
from tkinter import ttk

__all__ = ["LinkedSliderEntry"]


class LinkedSliderEntry:
    def __init__(self, parent, row, label, var, var_name, is_int, from_, to, step, pad=None):
        if pad is None:
            pad = {"padx": 6, "pady": 3}

        self.var = var
        self.var_name = var_name
        self.is_int = is_int
        self.from_ = from_
        self.to = to
        self.step = step

        self.label = ttk.Label(parent, text=label)
        self.label.grid(row=row, column=0, sticky="w", **pad)

        self.scale = tk.Scale(
            parent, from_=from_, to=to, resolution=step,
            orient="horizontal", showvalue=False,
            command=self._slider_cmd,
        )
        self.scale.set(var.get())
        self.scale.grid(row=row, column=1, sticky="ew", **pad)

        right = ttk.Frame(parent)
        right.grid(row=row, column=2, sticky="w", **pad)
        self._right = right

        self.btn_down = ttk.Button(right, text="\u25bc", width=2,
                                   command=lambda: self._step(-step))
        self.btn_down.pack(side="left")

        self.entry = ttk.Entry(right, width=8)
        self.entry.pack(side="left", padx=2)
        self.entry.insert(0, str(var.get()))

        self.btn_up = ttk.Button(right, text="\u25b2", width=2,
                                 command=lambda: self._step(step))
        self.btn_up.pack(side="left")

        self.entry.bind("<Return>", lambda ev: self._entry_commit())
        self.entry.bind("<FocusOut>", lambda ev: self._entry_commit())

    def set_visible(self, visible: bool):
        if visible:
            self.label.grid()
            self.scale.grid()
            self._right.grid()
        else:
            self.label.grid_remove()
            self.scale.grid_remove()
            self._right.grid_remove()

    def sync(self):
        v = self.var.get()
        self.scale.set(v)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(v))

    def _slider_cmd(self, val):
        v = int(float(val)) if self.is_int else round(float(val), 3)
        self.var.set(v)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(v))

    def _entry_commit(self):
        try:
            raw = self.entry.get().strip()
            v = int(raw) if self.is_int else round(float(raw), 3)
            v = max(self.from_, min(self.to, v))
        except ValueError:
            v = self.var.get()
        self.var.set(v)
        self.scale.set(v)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(v))

    def _step(self, delta):
        cur = self.var.get()
        nv = int(cur + delta) if self.is_int else round(cur + delta, 3)
        nv = max(self.from_, min(self.to, nv))
        self.var.set(nv)
        self.scale.set(nv)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(nv))

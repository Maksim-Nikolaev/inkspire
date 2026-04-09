"""Hover tooltip for any Tkinter widget."""

import tkinter as tk

__all__ = ["Tooltip"]


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event=None):
        if self._tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffdd", relief="solid", borderwidth=1,
            wraplength=320, padx=6, pady=4,
        )
        label.pack()

    def _hide(self, event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None

"""Hover tooltip for any Tkinter widget."""

import tkinter as tk

from ui import theme

__all__ = ["Tooltip"]


class Tooltip:
    DELAY_MS = 450

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self._tip = None
        self._pending = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self._pending = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self):
        if self._pending:
            self.widget.after_cancel(self._pending)
            self._pending = None

    def _show(self):
        self._pending = None

        if self._tip or not self.widget.winfo_exists():
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(background=theme.pick(theme.BORDER_STRONG))
        tk.Label(
            tw, text=self.text, justify="left", wraplength=300, padx=10, pady=7,
            background=theme.pick(theme.SURFACE), foreground=theme.pick(theme.TEXT_2),
            font=theme.font(12),
        ).pack(padx=1, pady=1)

    def _hide(self, event=None):
        self._cancel()

        if self._tip:
            self._tip.destroy()
            self._tip = None

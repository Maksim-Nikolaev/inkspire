"""Shared setup for Inkspire's secondary windows."""

import tkinter as tk

from ui import theme
from ui.theme import ctk

__all__ = ["Dialog"]


class Dialog(ctk.CTkToplevel):
    """A themed window placed over its parent; `modal=True` also grabs input until it closes."""

    def __init__(self, parent, title, modal=True, resizable=False):
        super().__init__(parent)
        self.title(title)
        self.resizable(resizable, resizable)
        self.transient(parent.winfo_toplevel())
        theme.apply_window_icon(self)

        self._parent = parent
        self._modal = modal

    def present(self):
        """Center over the parent, show, and grab input when modal."""
        self.update_idletasks()

        parent = self._parent.winfo_toplevel()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3

        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        self.after(20, self._activate)

    def _activate(self):
        try:
            if not self.winfo_viewable():
                self.after(20, self._activate)
                return

            self.focus_force()

            if self._modal:
                self.grab_set()
        except tk.TclError:
            pass

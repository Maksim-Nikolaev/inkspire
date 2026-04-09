"""About dialog showing version, author, and license information."""

import tkinter as tk
from tkinter import ttk

__all__ = ["AboutDialog"]

VERSION = "0.1.0"
AUTHOR = "Maksim Nikolaev"
REPO_URL = "https://github.com/Maksim-Nikolaev/inkspire"


class AboutDialog:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("About Inkspire")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        pad = {"padx": 16, "pady": 4}

        ttk.Label(self.win, text="Inkspire", font=("", 16, "bold")).pack(**pad)
        ttk.Label(self.win, text=f"Version {VERSION}").pack(**pad)
        ttk.Label(
            self.win,
            text="Traces line art by moving the mouse along\ncontours extracted from an image.",
            justify="center",
        ).pack(**pad)
        ttk.Label(self.win, text=f"Author: {AUTHOR}").pack(**pad)
        ttk.Label(self.win, text="License: MIT").pack(**pad)
        ttk.Label(self.win, text=REPO_URL, foreground="blue", cursor="hand2").pack(**pad)

        ttk.Button(self.win, text="Close", command=self.win.destroy).pack(pady=12)

        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.win.geometry(f"+{x}+{y}")

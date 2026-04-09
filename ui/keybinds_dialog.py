"""Dialog for viewing and changing keybinds."""

import tkinter as tk
from tkinter import ttk

__all__ = ["KeybindsDialog"]


class KeybindsDialog:
    def __init__(self, parent, config, on_update):
        self.config = config
        self.on_update = on_update
        self._capturing = None

        self.win = tk.Toplevel(parent)
        self.win.title("Keybinds")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        pad = {"padx": 12, "pady": 6}

        ttk.Label(self.win, text="Keybinds", font=("", 14, "bold")).pack(**pad)

        frame = ttk.Frame(self.win)
        frame.pack(**pad)

        ttk.Label(frame, text="Start / Pause:").grid(row=0, column=0, sticky="w", **pad)
        self._lbl_start = ttk.Label(frame, text=config.get("start_key", "F5"),
                                     width=12, relief="sunken", anchor="center")
        self._lbl_start.grid(row=0, column=1, **pad)
        self._btn_start = ttk.Button(frame, text="Set", width=5,
                                      command=lambda: self._start_capture("start_key", self._lbl_start, self._btn_start))
        self._btn_start.grid(row=0, column=2, **pad)

        ttk.Label(frame, text="Cancel:").grid(row=1, column=0, sticky="w", **pad)
        self._lbl_stop = ttk.Label(frame, text=config.get("stop_key", "Escape"),
                                    width=12, relief="sunken", anchor="center")
        self._lbl_stop.grid(row=1, column=1, **pad)
        self._btn_stop = ttk.Button(frame, text="Set", width=5,
                                     command=lambda: self._start_capture("stop_key", self._lbl_stop, self._btn_stop))
        self._btn_stop.grid(row=1, column=2, **pad)

        self._hint = ttk.Label(self.win, text="", foreground="gray")
        self._hint.pack(**pad)

        ttk.Button(self.win, text="Close", command=self.win.destroy).pack(pady=12)

        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.win.geometry(f"+{x}+{y}")

    def _start_capture(self, config_key, label, button):
        if self._capturing:
            self._cancel_capture()
        self._capturing = (config_key, label, button)
        button.config(text="...", state="disabled")
        self._hint.config(text="Press a key to bind, or click Close to cancel")
        self._key_binding = self.win.bind("<Key>", self._on_key)

    def _on_key(self, event):
        if not self._capturing:
            return
        config_key, label, button = self._capturing
        key_name = event.keysym
        self._cancel_capture()
        label.config(text=key_name)
        self.config[config_key] = key_name
        self.on_update(config_key, key_name)

    def _cancel_capture(self):
        if self._capturing:
            _, _, button = self._capturing
            button.config(text="Set", state="normal")
            self._capturing = None
            self._hint.config(text="")
            try:
                self.win.unbind("<Key>", self._key_binding)
            except Exception:
                self.win.unbind("<Key>")

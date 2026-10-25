"""Dialog for viewing and changing keybinds."""

from ui import theme
from ui.dialog import Dialog
from ui.theme import ctk
from ui.widgets import Card, button, key_label

__all__ = ["KeybindsDialog"]

_ROWS = [
    ("start_key", "Start / pause", "F5", "Starts drawing, then pauses and resumes it."),
    ("stop_key", "Cancel", "Escape", "Stops drawing and releases the mouse button."),
]


class KeybindsDialog:
    def __init__(self, parent, config, on_update):
        self.config = config
        self.on_update = on_update
        self._capturing = None
        self._key_binding = None
        self._chips = {}
        self._buttons = {}

        self.win = Dialog(parent, "Keybinds")
        self.win.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.win, text="Keybinds", font=theme.font(16, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 0))
        ctk.CTkLabel(
            self.win, text="These keys work globally, even while another app has focus.",
            text_color=theme.MUTED, anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        card = Card(self.win)
        card.grid(row=2, column=0, sticky="ew", padx=20)
        card.body.columnconfigure(0, weight=1)

        for row, (config_key, title, default, hint) in enumerate(_ROWS):
            text = ctk.CTkFrame(card.body, fg_color="transparent")
            text.grid(row=row, column=0, sticky="w", pady=6)
            ctk.CTkLabel(text, text=title, anchor="w", font=theme.font(13, "bold")).pack(anchor="w")
            ctk.CTkLabel(text, text=hint, anchor="w", text_color=theme.MUTED, font=theme.font(12)).pack(anchor="w")

            chip = ctk.CTkLabel(
                card.body, text=key_label(config.get(config_key, default)), font=theme.mono_font(12),
                fg_color=theme.SURFACE_3, text_color=theme.TEXT, corner_radius=6, width=72, height=30,
            )
            chip.grid(row=row, column=1, padx=(16, 8))
            self._chips[config_key] = chip

            change = button(card.body, "Change", lambda k=config_key: self._start_capture(k), width=96)
            change.grid(row=row, column=2)
            self._buttons[config_key] = change

        self._hint = ctk.CTkLabel(self.win, text="", text_color=theme.ACCENT_TEXT, anchor="w")
        self._hint.grid(row=3, column=0, sticky="w", padx=20, pady=(8, 0))

        button(self.win, "Done", self.win.destroy, kind="primary", width=96).grid(
            row=4, column=0, sticky="e", padx=20, pady=(8, 18))

        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)
        self.win.present()

    def _start_capture(self, config_key):
        if self._capturing:
            self._cancel_capture()

        self._capturing = config_key
        self._buttons[config_key].configure(text="Press a key…", state="disabled")
        self._hint.configure(text="Press the new key. Click Done to keep the current one.")
        self._key_binding = self.win.bind("<Key>", self._on_key)

    def _on_key(self, event):
        if not self._capturing:
            return

        config_key = self._capturing
        key_name = event.keysym

        self._cancel_capture()

        if not self.on_update(config_key, key_name):
            self._hint.configure(text=f"{key_label(key_name)} can't be used as a global key. Pick another one.")
            return

        self._chips[config_key].configure(text=key_label(key_name))
        self.config[config_key] = key_name

    def _cancel_capture(self):
        if not self._capturing:
            return

        self._buttons[self._capturing].configure(text="Change", state="normal")
        self._capturing = None
        self._hint.configure(text="")
        self.win.unbind("<Key>", self._key_binding)

"""First-launch explanation of macOS Accessibility access, polling until it is granted."""

from core import accessibility
from ui import theme
from ui.dialog import Dialog
from ui.theme import ctk
from ui.widgets import Card, Pill, button

__all__ = ["AccessibilityDialog"]

_STEPS = [
    "Click Open System Settings. macOS also shows its own prompt for Inkspire.",
    "Under Privacy & Security → Accessibility, switch Inkspire on.",
    "Come back here. This window closes by itself once access is granted.",
]


class AccessibilityDialog:
    def __init__(self, parent, on_granted=None):
        self._on_granted = on_granted
        self._poll_job = None

        self.win = Dialog(parent, "Allow mouse control", modal=False)
        self.win.columnconfigure(0, weight=1)

        ctk.CTkLabel(self.win, text="Allow Inkspire to control the mouse", font=theme.font(16, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            self.win, anchor="w", justify="left", wraplength=420, text_color=theme.TEXT_2,
            text="Inkspire draws by moving the pointer and holding a mouse button. "
                 "macOS only allows that for apps you switch on under Accessibility.",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        card = Card(self.win)
        card.grid(row=2, column=0, sticky="ew", padx=20)

        for index, step in enumerate(_STEPS, start=1):
            ctk.CTkLabel(
                card.body, text=str(index), width=22, height=22, corner_radius=11,
                fg_color=theme.ACCENT_SOFT, text_color=theme.ACCENT_TEXT, font=theme.font(12, "bold"),
            ).grid(row=index, column=0, sticky="nw", pady=4, padx=(0, 10))
            ctk.CTkLabel(card.body, text=step, anchor="w", justify="left", wraplength=360).grid(
                row=index, column=1, sticky="w", pady=4)

        ctk.CTkLabel(
            self.win, anchor="w", justify="left", wraplength=420, text_color=theme.MUTED, font=theme.font(12),
            text="Already switched on but nothing moves? Remove Inkspire from the list with − and add it again. "
                 "Unsigned builds need this after every update.",
        ).grid(row=3, column=0, sticky="w", padx=20, pady=(10, 0))

        footer = ctk.CTkFrame(self.win, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=20, pady=(14, 18))
        footer.columnconfigure(0, weight=1)
        self.status = Pill(footer, "Waiting for access", "warn")
        self.status.grid(row=0, column=0, sticky="w")
        button(footer, "Not now", self.close, kind="ghost", width=90).grid(row=0, column=1, padx=(0, 8))
        button(footer, "Open System Settings", self._open_settings, kind="primary").grid(row=0, column=2)

        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.present()
        self._poll()

    def _open_settings(self):
        accessibility.request_trust()
        accessibility.open_settings()

    def _poll(self):
        if accessibility.is_trusted():
            self.status.set("Access granted", "ok")

            if self._on_granted:
                self._on_granted()

            self._poll_job = self.win.after(900, self.close)

            return

        self._poll_job = self.win.after(1000, self._poll)

    def close(self):
        if self._poll_job:
            self.win.after_cancel(self._poll_job)
            self._poll_job = None

        if self.win.winfo_exists():
            self.win.destroy()

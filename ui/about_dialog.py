"""About dialog showing version, author, and license information."""

import webbrowser

from PIL import Image

from core.version import __version__
from ui import theme
from ui.dialog import Dialog
from ui.theme import ctk
from ui.widgets import button

__all__ = ["AboutDialog", "TAGLINE"]

AUTHOR = "Maksim Nikolaev"
REPO_URL = "https://github.com/Maksim-Nikolaev/inkspire"
LINKEDIN_URL = "https://www.linkedin.com/in/maksim-nikolaev-dev/"
TAGLINE = "Turns images, SVGs and text into line art your mouse draws in any app."


class AboutDialog:
    def __init__(self, parent):
        self.win = Dialog(parent, "About Inkspire")
        self.win.columnconfigure(0, weight=1)

        icon = Image.open(theme.icon_path("inkspire-256.png"))
        ctk.CTkLabel(self.win, text="", image=ctk.CTkImage(icon, size=(76, 76))).grid(row=0, column=0, pady=(24, 10))
        ctk.CTkLabel(self.win, text="Inkspire", font=theme.font(20, "bold")).grid(row=1, column=0)
        ctk.CTkLabel(self.win, text=f"Version {__version__}", text_color=theme.MUTED).grid(row=2, column=0)
        ctk.CTkLabel(
            self.win, text=TAGLINE, wraplength=300, justify="center", text_color=theme.TEXT_2,
        ).grid(row=3, column=0, padx=28, pady=(12, 12))
        ctk.CTkLabel(
            self.win, text=f"By {AUTHOR} · MIT License", text_color=theme.MUTED, font=theme.font(12),
        ).grid(row=4, column=0)

        links = ctk.CTkFrame(self.win, fg_color="transparent")
        links.grid(row=5, column=0, pady=(10, 0))

        for text, url in (("GitHub", REPO_URL), ("LinkedIn", LINKEDIN_URL)):
            button(
                links, text, lambda u=url: webbrowser.open(u), kind="ghost", width=92,
                text_color=theme.ACCENT,
            ).pack(side="left", padx=4)

        button(self.win, "Close", self.win.destroy, width=120).grid(row=6, column=0, pady=(12, 22))

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.present()

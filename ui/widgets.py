"""Building blocks shared by the main window and dialogs: cards, slider rows, toggles, buttons, chips."""

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter

from ui import theme
from ui.theme import ctk
from ui.tooltip import Tooltip

__all__ = [
    "button", "Card", "SliderRow", "Toggle", "ToggleRow", "Segmented", "kbd", "key_label",
    "Pill", "FontList", "AutoScrollFrame",
]

_BUTTON_STYLES = {
    "primary": {
        "fg_color": theme.ACCENT, "hover_color": theme.ACCENT_HOVER,
        "text_color": theme.ON_ACCENT, "border_width": 0,
    },
    "secondary": {
        "fg_color": theme.SURFACE, "hover_color": theme.SURFACE_2, "text_color": theme.TEXT,
        "border_width": 1, "border_color": theme.BORDER_STRONG,
    },
    "ghost": {
        "fg_color": "transparent", "hover_color": theme.SURFACE_3,
        "text_color": theme.TEXT_2, "border_width": 0,
    },
    "danger": {
        "fg_color": theme.SURFACE, "hover_color": theme.DANGER_SOFT, "text_color": theme.DANGER,
        "border_width": 1, "border_color": theme.BORDER_STRONG,
    },
}

_KEY_LABELS = {
    "Escape": "Esc", "Return": "Enter", "Prior": "PgUp", "Next": "PgDn",
    "BackSpace": "Backspace", "space": "Space", "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Alt_L": "Alt", "Alt_R": "Alt", "Shift_L": "Shift", "Shift_R": "Shift",
}

_PILL_TONES = {
    "neutral": (theme.SURFACE_2, theme.TEXT_2),
    "accent": (theme.ACCENT_SOFT, theme.ACCENT_TEXT),
    "ok": (theme.OK_SOFT, theme.OK),
    "warn": (theme.WARN_SOFT, theme.WARN),
    "danger": (theme.DANGER_SOFT, theme.DANGER),
}


def button(parent, text, command=None, kind="secondary", **kwargs):
    options = {
        "height": 32,
        "corner_radius": theme.RADIUS,
        "font": theme.font(13, "bold" if kind == "primary" else "normal"),
        **_BUTTON_STYLES[kind],
        **kwargs,
    }

    return ctk.CTkButton(parent, text=text, command=command, **options)


def key_label(keysym: str) -> str:
    if keysym in _KEY_LABELS:
        return _KEY_LABELS[keysym]

    return keysym.upper() if len(keysym) == 1 else keysym


def kbd(parent, text):
    return ctk.CTkLabel(
        parent, text=text, font=theme.mono_font(11), text_color=theme.TEXT_2,
        fg_color=theme.SURFACE_3, corner_radius=5, height=20, width=26,
    )


class Card(ctk.CTkFrame):
    """A rounded, bordered section with an uppercase caption. Children go into `body`."""

    def __init__(self, parent, title=None, **kwargs):
        super().__init__(
            parent, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER,
            corner_radius=theme.CARD_RADIUS, **kwargs,
        )
        self.columnconfigure(0, weight=1)

        if title:
            ctk.CTkLabel(
                self, text=title.upper(), font=theme.font(11, "bold"), text_color=theme.MUTED,
                anchor="w", height=18,
            ).grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        self.body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4 if title else 14, 14))
        self.body.columnconfigure(1, weight=1)


class SliderRow:
    """Label, slider and value field on one grid row, kept in sync with a Tk variable."""

    def __init__(self, parent, row, label, var, is_int, from_, to, step, tooltip=None):
        self.var = var
        self.is_int = is_int
        self.from_ = from_
        self.to = to
        self.step = step
        self._decimals = 0 if is_int else max(0, -math.floor(math.log10(step)))

        self.label = ctk.CTkLabel(parent, text=label, text_color=theme.TEXT_2, anchor="w", font=theme.font(13))
        self.label.grid(row=row, column=0, sticky="w", pady=3, padx=(0, 12))

        self.slider = ctk.CTkSlider(
            parent, from_=from_, to=to, number_of_steps=max(1, round((to - from_) / step)),
            command=self._slider_cmd, height=18,
        )
        self.slider.grid(row=row, column=1, sticky="ew", pady=3)

        # The wheel scrolls the sidebar; letting sliders take it would change settings while scrolling.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.slider._canvas.unbind(sequence)

        self.entry = ctk.CTkEntry(parent, width=60, height=28, justify="right", font=theme.mono_font(12))
        self.entry.grid(row=row, column=2, sticky="e", pady=3, padx=(12, 0))

        self.entry.bind("<Return>", lambda e: self._entry_commit())
        self.entry.bind("<FocusOut>", lambda e: self._entry_commit())
        self.entry.bind("<Up>", lambda e: self._step(step))
        self.entry.bind("<Down>", lambda e: self._step(-step))

        if tooltip:
            Tooltip(self.label, tooltip)

        self.sync()

    def set_visible(self, visible: bool):
        for widget in (self.label, self.slider, self.entry):
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def sync(self):
        value = self.var.get()

        self.slider.set(value)
        self._write_entry(value)

    def _format(self, value):
        return str(int(value)) if self.is_int else f"{value:.{self._decimals}f}"

    def _write_entry(self, value):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, self._format(value))

    def _coerce(self, value):
        value = max(self.from_, min(self.to, value))

        return int(round(value)) if self.is_int else round(value, self._decimals)

    def _slider_cmd(self, value):
        value = self._coerce(float(value))

        self.var.set(value)
        self._write_entry(value)

    def _entry_commit(self):
        try:
            value = self._coerce(float(self.entry.get().strip().replace(",", ".")))
        except ValueError:
            value = self.var.get()

        if value != self.var.get():
            self.var.set(value)

        self.sync()

    def _step(self, delta):
        value = self._coerce(self.var.get() + delta)

        self.var.set(value)
        self.sync()

        return "break"


def _switch_image(on, dark, width=36, height=20, ss=4):
    w, h = width * ss, height * ss
    track = theme.ACCENT[dark] if on else theme.BORDER_STRONG[dark]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=track)

    inset = 2 * ss
    d = h - 2 * inset
    x = w - inset - d if on else inset
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((x, inset + ss // 2, x + d, inset + d + ss // 2), fill=(0, 0, 0, 70))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(ss)))
    ImageDraw.Draw(img).ellipse((x, inset, x + d, inset + d), fill="#ffffff")

    return img


class Toggle(ctk.CTkLabel):
    """An on/off switch bound to a BooleanVar, drawn from anti-aliased images."""

    _images = {}

    def __init__(self, parent, variable, width=36, height=20):
        super().__init__(parent, text="", width=width, height=height, cursor="hand2")
        self._bound_var = variable
        self._size = (width, height)

        self.bind("<Button-1>", lambda e: self.toggle())
        variable.trace_add("write", lambda *_: self._render())
        self._render()

    def toggle(self):
        self._bound_var.set(not self._bound_var.get())

    def _render(self):
        on = bool(self._bound_var.get())
        key = (on, self._size)

        if key not in Toggle._images:
            Toggle._images[key] = ctk.CTkImage(
                light_image=_switch_image(on, 0, *self._size), dark_image=_switch_image(on, 1, *self._size), size=self._size,
            )

        self.configure(image=Toggle._images[key])


class ToggleRow(ctk.CTkFrame):
    """A label on the left and a switch on the right, bound to a BooleanVar."""

    def __init__(self, parent, text, variable, tooltip=None):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.columnconfigure(0, weight=1)

        self.switch = Toggle(self, variable)
        self.switch.grid(row=0, column=1, sticky="e")

        self.label = ctk.CTkLabel(self, text=text, text_color=theme.TEXT_2, anchor="w", font=theme.font(13), cursor="hand2")
        self.label.grid(row=0, column=0, sticky="w")
        self.label.bind("<Button-1>", lambda e: self.switch.toggle())

        if tooltip:
            Tooltip(self.label, tooltip)


class Segmented(ctk.CTkSegmentedButton):
    """Segmented control bound to a Tk variable, showing labels for stored values."""

    def __init__(self, parent, options, variable, command=None, **kwargs):
        self._option_labels = dict(options)
        self._option_values = {label: value for value, label in options}
        self._bound_var = variable
        self._on_change = command

        super().__init__(
            parent, values=[label for _, label in options], command=self._on_select,
            height=30, font=theme.font(12), dynamic_resizing=False, **kwargs,
        )

        self._sync()
        variable.trace_add("write", lambda *_: self._sync())

    def _on_select(self, label):
        self._bound_var.set(self._option_values[label])

        if self._on_change:
            self._on_change(self._option_values[label])

    def _sync(self):
        label = self._option_labels.get(self._bound_var.get())

        if label and self.get() != label:
            self.set(label)


class Pill(ctk.CTkLabel):
    """A small rounded badge whose tone can change."""

    def __init__(self, parent, text="", tone="neutral", **kwargs):
        super().__init__(parent, text=text, corner_radius=999, height=22, font=theme.font(12), **kwargs)
        self.set(text, tone)

    def set(self, text, tone="neutral"):
        background, foreground = _PILL_TONES[tone]

        self.configure(text=f"  {text}  ", fg_color=background, text_color=foreground)


class FontList(ctk.CTkFrame):
    """Search field over a short list of font families."""

    def __init__(self, parent, on_select, rows=6):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.columnconfigure(0, weight=1)

        self._families = []
        self._shown = []
        self._on_select = on_select

        self.search = ctk.CTkEntry(self, placeholder_text="Search fonts", height=30)
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", lambda e: self._filter())
        self.search.bind("<Return>", lambda e: self._pick_first())
        self.search.bind("<Down>", lambda e: self._focus_list())

        self._frame = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER_STRONG, corner_radius=theme.RADIUS)
        self._frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self._frame.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(self._frame, height=rows, activestyle="none", exportselection=False, borderwidth=0, highlightthickness=0, font=theme.font(13))
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_listbox_select())

        self._scrollbar = ctk.CTkScrollbar(self._frame, command=self.listbox.yview, width=12, height=40)
        self._scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 3), pady=6)
        self.listbox.configure(yscrollcommand=self._scrollbar.set)

        self.refresh_theme()

    def refresh_theme(self):
        self.listbox.configure(
            background=theme.pick(theme.SURFACE), foreground=theme.pick(theme.TEXT),
            selectbackground=theme.pick(theme.ACCENT_SOFT), selectforeground=theme.pick(theme.ACCENT_TEXT),
        )

    def set_families(self, families):
        self._families = list(families)
        self._filter()

    def select(self, family):
        if family not in self._shown:
            self.search.delete(0, tk.END)
            self._filter()

        if family in self._shown:
            index = self._shown.index(family)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(index)
            self.listbox.see(index)

    def get(self):
        selection = self.listbox.curselection()

        return self._shown[selection[0]] if selection else None

    def _filter(self):
        query = self.search.get().strip().lower()
        current = self.get()

        self._shown = [f for f in self._families if query in f.lower()]
        self.listbox.delete(0, tk.END)

        for family in self._shown:
            self.listbox.insert(tk.END, family)

        if current in self._shown:
            index = self._shown.index(current)
            self.listbox.selection_set(index)
            self.listbox.see(index)

    def _pick_first(self):
        if self._shown and not self.listbox.curselection():
            self.listbox.selection_set(0)
            self._on_listbox_select()

    def _focus_list(self):
        if self._shown:
            self.listbox.focus_set()

            if not self.listbox.curselection():
                self.listbox.selection_set(0)
                self._on_listbox_select()

    def _on_listbox_select(self):
        family = self.get()

        if family:
            self._on_select(family)


class AutoScrollFrame(ctk.CTkScrollableFrame):
    """Scrollable frame whose scrollbar only shows while the content overflows."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._scrollbar_shown = True
        self._parent_canvas.bind("<Configure>", lambda e: self.after_idle(self._update_scrollbar), add="+")
        self.bind("<Configure>", lambda e: self.after_idle(self._update_scrollbar), add="+")

    def _update_scrollbar(self):
        if not self.winfo_exists():
            return

        overflow = self.winfo_reqheight() > self._parent_canvas.winfo_height() + 1

        if overflow and not self._scrollbar_shown:
            self._scrollbar.grid()
            self._scrollbar_shown = True
        elif not overflow and self._scrollbar_shown:
            self._scrollbar.grid_remove()
            self._parent_canvas.yview_moveto(0)
            self._scrollbar_shown = False

    def _check_if_valid_scroll(self, widget):
        while widget is not None:
            if widget == self._parent_canvas:
                return True

            if isinstance(widget, (ctk.CTkScrollbar, ctk.CTkTextbox, tk.Listbox)):
                return False

            widget = widget.master

        return False

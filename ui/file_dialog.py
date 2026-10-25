"""Open-file dialogs: the desktop's own picker on Linux (kdialog or zenity), Tk's native one elsewhere."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tkinter import filedialog

from core.proc import system_env

__all__ = ["ask_open_filename"]

_last_dir = str(Path.home())
_busy = False


def ask_open_filename(parent, title, filetypes) -> str:
    """Return the chosen path, or an empty string when the user cancels."""
    global _last_dir, _busy

    if _busy:
        return ""

    path = None

    if sys.platform.startswith("linux"):
        command = _linux_command(parent, title, filetypes)

        if command:
            _busy = True

            try:
                path = _run_blocking(parent, command)
            finally:
                _busy = False

    if path is None:
        path = filedialog.askopenfilename(parent=parent, title=title, filetypes=filetypes, initialdir=_last_dir)

    if path:
        _last_dir = str(Path(path).parent)

    return path or ""


def _linux_command(parent, title, filetypes):
    kde = "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")
    kdialog = shutil.which("kdialog")
    zenity = shutil.which("zenity")

    if kdialog and (kde or not zenity):
        filters = "\n".join(f"{label} ({patterns.replace('*.*', '*')})" for label, patterns in filetypes)
        command = [kdialog, "--title", title, "--getopenfilename", _last_dir, filters]

        if os.environ.get("XDG_SESSION_TYPE") == "x11":
            command[1:1] = ["--attach", str(int(parent.winfo_toplevel().wm_frame(), 16))]

        return command

    if zenity:
        command = [zenity, "--file-selection", f"--title={title}", f"--filename={_last_dir}/"]
        command += [f"--file-filter={label} | {patterns.replace('*.*', '*')}" for label, patterns in filetypes]

        return command

    return None


def _run_blocking(parent, command):
    """Run the picker while keeping Tk responsive. Returns None when the picker itself failed."""
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=system_env())
    except OSError:
        return None

    while proc.poll() is None:
        parent.update()
        time.sleep(0.03)

    output = proc.stdout.read().strip()

    if proc.returncode == 0:
        return output.splitlines()[0] if output else ""

    if proc.returncode == 1:
        return ""

    return None

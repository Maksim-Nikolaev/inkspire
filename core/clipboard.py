"""Platform-aware clipboard image extraction."""

import subprocess
import io
import sys
from PIL import Image

from core.proc import system_env

__all__ = ["get_clipboard_image"]


def get_clipboard_image():
    """Get an image from the system clipboard.

    Returns a PIL Image or None if no image is available.
    """
    # PIL ImageGrab works natively on Windows and macOS, and on Linux with xclip/wl-paste
    try:
        from PIL import ImageGrab

        img = ImageGrab.grabclipboard()

        if img is not None:
            return img
    except Exception:
        pass

    if sys.platform in ("win32", "darwin"):
        return None

    for mime in ["image/png", "image/bmp", "image/jpeg"]:
        try:
            data = subprocess.check_output(
                ["xclip", "-selection", "clipboard", "-t", mime, "-o"],
                stderr=subprocess.DEVNULL, env=system_env())

            return Image.open(io.BytesIO(data))
        except Exception:
            continue

    try:
        data = subprocess.check_output(
            ["xsel", "--clipboard", "--output"],
            stderr=subprocess.DEVNULL, env=system_env())

        return Image.open(io.BytesIO(data))
    except Exception:
        pass

    try:
        data = subprocess.check_output(
            ["wl-paste", "--type", "image/png"],
            stderr=subprocess.DEVNULL, env=system_env())

        return Image.open(io.BytesIO(data))
    except Exception:
        pass

    return None

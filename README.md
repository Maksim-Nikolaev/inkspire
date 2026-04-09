# Inkspire

Inkspire traces line art by moving the mouse along contours extracted from
images, SVGs, or text. It drives drawing applications that accept synthetic
pointer input, using native `ctypes` calls for low-latency mouse control on
both Linux (X11) and Windows.

## Features

- **Multiple detection modes** — threshold, Canny edge, adaptive threshold,
  and auto-detect for black & white line art, colored images, and halftones.
- **Text and SVG input** — render text from system fonts or load SVG paths
  directly, in a separate tab with independent settings.
- **Cross-platform** — Linux (X11) and Windows, with native mouse and
  keyboard control via `ctypes`.
- **Canvas picker** — drag-to-select your target drawing area on screen.
- **Live preview** — real-time contour preview with adjustable parameters.
- **Pause/resume** — F5 toggles start, pause, and resume. Escape cancels.
- **Path optimization** — optional nearest-neighbor reordering to minimize
  pen-up travel between contours.
- **Session persistence** — settings, source file, and tab state are
  restored automatically on next launch.
- **Customizable keybinds** — reassign start/pause and cancel keys from
  the Keybinds dialog.

## Requirements

- Python 3.10+
- **Linux:** X11 session, system packages:
  ```bash
  sudo apt install python3-tk python3-pil.imagetk libx11-6 libxtst6 xclip
  ```
- **Windows:** no extra system packages needed.
- Python packages:
  ```bash
  pip install .
  ```

## Usage

```bash
python3 main.py
```

1. Load an image, paste from clipboard, browse an SVG, or type text.
2. Adjust detection mode and parameters (live preview updates automatically).
3. Optionally use **Set Canvas** to drag-select your target drawing area.
4. Press **F5** (or click Start Drawing) to begin. F5 pauses/resumes, Escape cancels.

## License

Released under the [MIT License](LICENSE).

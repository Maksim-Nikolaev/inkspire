# Inkspire

Inkspire traces line art by moving the mouse along contours extracted from an
image. It uses fast, jitter-free X11 `ctypes` calls for mouse control, making
it suitable for driving drawing applications that accept synthetic pointer
input.

> **Status:** early prototype. Source lives in `main.py` with supporting
> modules under `ui/`, `detection/`, and `drawing/`.

## Features

- Multiple detection modes for black & white line art, colored images, and
  halftones.
- Direct X11 mouse control via `libX11` / `libXtst` for low-latency tracing.
- Simple Tkinter GUI for loading images and starting/stopping traces.
- Escape key interrupt for aborting an in-progress trace.

## Requirements

- Linux with an X11 session (Wayland is not supported).
- Python 3.9+
- System packages:
  ```bash
  sudo apt install python3-tk python3-pil.imagetk libx11-6 libxtst6
  ```
- Python packages:
  ```bash
  pip install -r requirements.txt
  ```

## Usage

```bash
python3 main.py
```

> **Note:** On some X11 configurations, mouse synthesis may require running
> with `sudo`. Try without first.

1. Load an image via the GUI.
2. Pick a detection mode appropriate for the artwork.
3. Position the target application (e.g. a drawing canvas).
4. Start the trace. Press **Escape** at any time to abort.

## License

Released under the [MIT License](LICENSE).

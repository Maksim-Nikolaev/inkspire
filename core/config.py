"""Load and save user configuration as JSON."""

import json
from pathlib import Path

__all__ = ["load_config", "save_config", "load_session", "save_session", "CONFIG_DIR"]

CONFIG_DIR = Path.home() / ".config" / "inkspire"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_FILE = CONFIG_DIR / "session.json"

DEFAULTS = {
    "stop_key": "Escape",
    "start_key": "F5",
    "scale": 1.0,
    "offset_x": 200,
    "offset_y": 200,
    "speed": 500,
    "mouse_button": "right",
    "delay_before": 3,
    "relative_offset": True,
    "auto_preview": True,
}


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    # Migrate old seconds-per-point speed to pts/s
    if config.get("speed", 500) < 1:
        old = config["speed"]
        config["speed"] = max(10, min(10000, int(1.0 / old))) if old > 0 else 500
    return config


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_session() -> dict | None:
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_session(session: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)

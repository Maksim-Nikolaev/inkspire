"""Load and save user configuration as JSON."""

import json
from pathlib import Path

__all__ = ["load_config", "save_config", "CONFIG_DIR"]

CONFIG_DIR = Path.home() / ".config" / "inkspire"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "stop_key": "Escape",
    "start_key": "F5",
}


def load_config() -> dict:
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

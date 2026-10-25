"""Environment for launching system tools from a bundled (PyInstaller) build."""

import os
import sys

__all__ = ["system_env"]


def system_env() -> dict:
    """Copy of os.environ without the bundle's library path, so system binaries load system libraries."""
    env = dict(os.environ)

    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(f"{var}_ORIG", None)

        if original is not None:
            env[var] = original
        elif getattr(sys, "frozen", False):
            env.pop(var, None)

    return env

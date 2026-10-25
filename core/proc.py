"""Environment for launching system tools from a bundled (PyInstaller) build."""

import os
import sys

__all__ = ["restore_system_env"]


def restore_system_env():
    """Drop the bundle's library path from os.environ, so every system binary we launch loads system libraries."""
    # The dynamic loader reads these only at process start, so the running process keeps resolving bundled libraries.
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = os.environ.pop(f"{var}_ORIG", None)

        if original is not None:
            os.environ[var] = original
        elif getattr(sys, "frozen", False):
            os.environ.pop(var, None)

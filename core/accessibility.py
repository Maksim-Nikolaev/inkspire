"""macOS Accessibility (TCC) permission, which posting synthetic mouse events requires."""

import ctypes
import subprocess
import sys

__all__ = ["needs_permission", "is_trusted", "request_trust", "open_settings"]

_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

_ax = None
_cf = None

if sys.platform == "darwin":
    try:
        _ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        _cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        _ax.AXIsProcessTrusted.argtypes = []
        _ax.AXIsProcessTrusted.restype = ctypes.c_bool
        _ax.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        _ax.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        _cf.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
        ]
        _cf.CFDictionaryCreate.restype = ctypes.c_void_p
        _cf.CFRelease.argtypes = [ctypes.c_void_p]
        _cf.CFRelease.restype = None
    except (OSError, AttributeError):
        _ax = None


def needs_permission() -> bool:
    return _ax is not None


def is_trusted() -> bool:
    if _ax is None:
        return True

    return bool(_ax.AXIsProcessTrusted())


def request_trust() -> bool:
    """Ask macOS to show its Accessibility prompt and list Inkspire in System Settings."""
    if _ax is None:
        return True

    prompt_key = ctypes.c_void_p.in_dll(_ax, "kAXTrustedCheckOptionPrompt")
    true_value = ctypes.c_void_p.in_dll(_cf, "kCFBooleanTrue")
    keys = (ctypes.c_void_p * 1)(prompt_key.value)
    values = (ctypes.c_void_p * 1)(true_value.value)
    options = _cf.CFDictionaryCreate(
        None, keys, values, 1,
        ctypes.addressof(ctypes.c_void_p.in_dll(_cf, "kCFTypeDictionaryKeyCallBacks")),
        ctypes.addressof(ctypes.c_void_p.in_dll(_cf, "kCFTypeDictionaryValueCallBacks")),
    )

    try:
        return bool(_ax.AXIsProcessTrustedWithOptions(options))
    finally:
        if options:
            _cf.CFRelease(options)


def open_settings():
    subprocess.Popen(["open", _SETTINGS_URL])

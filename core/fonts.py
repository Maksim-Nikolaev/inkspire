"""Discover system fonts (TTF/OTF) across platforms."""

import sys
from pathlib import Path

__all__ = ["discover_fonts"]

_cache = None


def discover_fonts() -> list[dict]:
    """Scan system font directories and return available fonts.

    Returns list of dicts: [{"family": str, "style": str, "path": str}, ...]
    Sorted by family name. Cached after first call.
    """
    global _cache
    if _cache is not None:
        return _cache

    dirs = _font_dirs()
    fonts = []
    seen = set()

    for d in dirs:
        p = Path(d)
        if not p.is_dir():
            continue
        for f in p.rglob("*"):
            if f.suffix.lower() not in (".ttf", ".otf"):
                continue
            path_str = str(f)
            if path_str in seen:
                continue
            seen.add(path_str)
            info = _read_font_name(f)
            if info:
                fonts.append(info)

    fonts.sort(key=lambda x: (x["family"].lower(), x["style"].lower()))
    _cache = fonts
    return fonts


def _font_dirs() -> list[str]:
    platform = sys.platform
    if platform == "win32":
        windir = Path("C:/Windows/Fonts")
        user = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
        return [str(windir), str(user)]
    elif platform == "darwin":
        return [
            "/Library/Fonts",
            str(Path.home() / "Library" / "Fonts"),
            "/System/Library/Fonts",
        ]
    else:  # Linux
        return [
            "/usr/share/fonts",
            str(Path.home() / ".local" / "share" / "fonts"),
            str(Path.home() / ".fonts"),
        ]


def _read_font_name(path: Path) -> dict | None:
    """Read font family and style from a font file via fonttools."""
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(str(path), fontNumber=0)
        name_table = font["name"]
        family = None
        style = None
        for record in name_table.names:
            if record.nameID == 1 and family is None:
                family = record.toUnicode()
            elif record.nameID == 2 and style is None:
                style = record.toUnicode()
            if family and style:
                break
        font.close()
        if family:
            return {"family": family, "style": style or "Regular", "path": str(path)}
    except Exception:
        pass
    return None

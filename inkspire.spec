# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Inkspire. Run: pyinstaller inkspire.spec

Linux and Windows get a single-file executable, macOS gets Inkspire.app.
Set INKSPIRE_CODESIGN_IDENTITY to sign the macOS app with a Developer ID; without it the app is ad-hoc signed.
"""

import os
import platform
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

sys.path.insert(0, SPECPATH)
from core.version import __version__

hiddenimports = (
    collect_submodules("core")
    + collect_submodules("detection")
    + collect_submodules("drawing")
    + collect_submodules("ui")
    + ["PIL._tkinter_finder"]
)
datas = collect_data_files("customtkinter") + [("ui/icons", "ui/icons")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas", "IPython", "jupyter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

if sys.platform == "darwin":
    identity = os.environ.get("INKSPIRE_CODESIGN_IDENTITY") or None

    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Inkspire",
        debug=False,
        strip=False,
        upx=False,
        console=False,
        argv_emulation=False,
        codesign_identity=identity,
        entitlements_file="packaging/entitlements.plist" if identity else None,
        icon="assets/icon/inkspire.icns",
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Inkspire")
    app = BUNDLE(
        coll,
        name="Inkspire.app",
        icon="assets/icon/inkspire.icns",
        bundle_identifier="com.rombikro.inkspire",
        version=__version__,
        info_plist={
            "CFBundleName": "Inkspire",
            "CFBundleDisplayName": "Inkspire",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSApplicationCategoryType": "public.app-category.graphics-design",
            "LSMinimumSystemVersion": "14.0" if platform.machine() == "x86_64" else "13.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "NSHumanReadableCopyright": "© Maksim Nikolaev. MIT License.",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="inkspire",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        icon="ui/icons/inkspire.ico",
    )

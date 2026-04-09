#!/usr/bin/env bash
set -euo pipefail

VENV=".venv-build"

echo "=== Inkspire build ==="

# Create/reuse a build venv
if [ ! -d "$VENV" ]; then
    echo "Creating build venv..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

# Install deps
pip install --quiet opencv-python numpy Pillow fonttools pyinstaller

# Clean previous build
rm -rf build/ dist/

# Build single-file executable
pyinstaller inkspire.spec

SIZE=$(du -h dist/inkspire* | head -1 | cut -f1)
echo ""
echo "=== Done: dist/inkspire ($SIZE) ==="
echo "Run: ./dist/inkspire"

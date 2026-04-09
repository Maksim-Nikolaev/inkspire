#!/usr/bin/env bash
set -euo pipefail

VENV=".venv-build"
OUT="builds"

echo "=== Inkspire build ==="

# Create/reuse a build venv
if [ ! -d "$VENV" ]; then
    echo "Creating build venv..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

# Install deps
pip install --quiet "opencv-python" "numpy" "Pillow" "fonttools" "pyinstaller"

# Clean previous build
rm -rf build/ dist/

# Build single-file executable
pyinstaller inkspire.spec

# Package
mkdir -p "$OUT"
chmod +x dist/inkspire
tar -czf "$OUT/inkspire-linux.tar.gz" -C dist inkspire

SIZE=$(du -h "$OUT/inkspire-linux.tar.gz" | cut -f1)
echo ""
echo "=== Done: $OUT/inkspire-linux.tar.gz ($SIZE) ==="
echo "Extract and run: tar xzf inkspire-linux.tar.gz && ./inkspire"

#!/usr/bin/env bash
set -euo pipefail

VENV=".venv-build"
OUT="builds"

echo "=== Inkspire build ==="

if [ ! -d "$VENV" ]; then
    echo "Creating build venv..."
    python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"

pip install --quiet -r requirements.txt "pyinstaller>=6.0"

rm -rf build/ dist/

pyinstaller --noconfirm inkspire.spec

mkdir -p "$OUT"
if [ "$(uname)" = "Darwin" ]; then
    ARTIFACT="$OUT/inkspire-macos-$(uname -m).dmg"
    packaging/make_dmg.sh dist/Inkspire.app "$ARTIFACT"
    HINT="Open the .dmg and drag Inkspire to Applications"
else
    ARTIFACT="$OUT/inkspire-linux.tar.gz"
    chmod +x dist/inkspire
    tar -czf "$ARTIFACT" -C dist inkspire
    HINT="Extract and run: tar xzf inkspire-linux.tar.gz && ./inkspire"
fi

SIZE=$(du -h "$ARTIFACT" | cut -f1)
echo ""
echo "=== Done: $ARTIFACT ($SIZE) ==="
echo "$HINT"

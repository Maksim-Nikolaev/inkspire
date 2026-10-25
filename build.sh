#!/usr/bin/env bash
# Usage: ./build.sh            build for this machine into builds/ (Linux, macOS, or Windows in Git Bash)
#        ./build.sh --docker   Linux release build inside Ubuntu 22.04, so the binary also runs on older distros
set -euo pipefail

OUT="builds"
VENV="${VENV:-.venv-build}"

case "$(uname -s)" in
    Darwin) PLATFORM=macos BINARY=dist/Inkspire.app/Contents/MacOS/Inkspire ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM=windows BINARY=dist/inkspire.exe ;;
    *) PLATFORM=linux BINARY=dist/inkspire ;;
esac

build() {
    if [ "$PLATFORM" = windows ]; then
        PYTHON="${PYTHON:-py -3.13}"
        ACTIVATE="$VENV/Scripts/activate"
    else
        PYTHON="${PYTHON:-python3}"
        ACTIVATE="$VENV/bin/activate"
    fi

    if [ ! -d "$VENV" ]; then
        echo "Creating build venv..."
        $PYTHON -m venv "$VENV"
    fi

    source "$ACTIVATE"
    pip install --quiet -r requirements.txt "pyinstaller>=6.0"

    if ! python -c "import sys, tkinter; sys.exit(tkinter.TkVersion >= 9)"; then
        echo "This Python ships Tk 9, which CustomTkinter is not tested against. Build with Python 3.13, e.g. PYTHON=python3.13 ./build.sh" >&2
        exit 1
    fi

    rm -rf build/ dist/
    pyinstaller --noconfirm inkspire.spec
}

self_test() {
    if [ "$PLATFORM" = linux ] && [ -z "${DISPLAY:-}" ]; then
        echo "No display, skipping the self-test."
        return
    fi

    "$BINARY" --self-test
}

package() {
    mkdir -p "$OUT"

    case "$PLATFORM" in
        macos)
            ARTIFACT="$OUT/inkspire-macos-$(uname -m).dmg"
            packaging/make_dmg.sh dist/Inkspire.app "$ARTIFACT"
            ;;
        windows)
            ARTIFACT="$OUT/inkspire.exe"
            cp dist/inkspire.exe "$ARTIFACT"
            ;;
        linux)
            ARTIFACT="$OUT/inkspire.tar.gz"
            chmod +x dist/inkspire
            cp ui/icons/inkspire-256.png dist/inkspire.png
            tar -czf "$ARTIFACT" -C dist inkspire inkspire.png
            ;;
    esac

    echo "=== Done: $ARTIFACT ($(du -h "$ARTIFACT" | cut -f1)) ==="
}

echo "=== Inkspire build ($PLATFORM) ==="

if [ "${1:-}" = "--docker" ]; then
    docker build -t inkspire-build -f packaging/linux.Dockerfile .
    docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/src" -w /src inkspire-build ./build.sh
    self_test
    exit
fi

build
self_test
package

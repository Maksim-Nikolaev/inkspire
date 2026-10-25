#!/bin/sh
# Installs or updates Inkspire on Linux and macOS from the latest GitHub release.
#   curl -fsSL https://raw.githubusercontent.com/Maksim-Nikolaev/inkspire/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/Maksim-Nikolaev/inkspire/main/install.sh | sh -s -- --uninstall
# INKSPIRE_VERSION=v0.6.0 installs that release instead of the latest one.
set -eu

REPO="Maksim-Nikolaev/inkspire"
VERSION="${INKSPIRE_VERSION:-latest}"
BUNDLE_ID="com.rombikro.inkspire"

BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_FILE="$DATA_DIR/applications/inkspire.desktop"
ICON_FILE="$DATA_DIR/icons/hicolor/256x256/apps/inkspire.png"

if [ "$VERSION" = latest ]; then
    BASE="https://github.com/$REPO/releases/latest/download"
else
    BASE="https://github.com/$REPO/releases/download/$VERSION"
fi

say() {
    printf '%s\n' "$*"
}

die() {
    printf 'inkspire: %s\n' "$*" >&2
    exit 1
}

usage() {
    say "Usage: install.sh [--uninstall]"
    say "Installs or updates Inkspire from the latest GitHub release. Set INKSPIRE_VERSION=v0.6.0 to pick another release."
}

download() {
    say "Downloading $1"

    if command -v curl >/dev/null 2>&1; then
        curl -fL --progress-bar -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q --show-progress -O "$2" "$1"
    else
        die "curl or wget is required"
    fi
}

refresh_desktop_caches() {
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q "$DATA_DIR/applications" 2>/dev/null || true
    fi

    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t "$DATA_DIR/icons/hicolor" 2>/dev/null || true
    fi
}

install_linux() {
    [ "$(uname -m)" = x86_64 ] || die "release builds exist for x86_64 only; see https://github.com/$REPO#run-from-source"

    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT

    download "$BASE/inkspire.tar.gz" "$TMP/inkspire.tar.gz" || die "download failed: $BASE/inkspire.tar.gz"
    tar -xzf "$TMP/inkspire.tar.gz" -C "$TMP"

    # Releases before v0.6.0 ship the binary without an icon.
    if [ ! -f "$TMP/inkspire.png" ]; then
        download "https://raw.githubusercontent.com/$REPO/main/ui/icons/inkspire-256.png" "$TMP/inkspire.png" || rm -f "$TMP/inkspire.png"
    fi

    mkdir -p "$BIN_DIR" "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"

    # Renaming over the old binary keeps a running Inkspire working until it exits.
    cp "$TMP/inkspire" "$BIN_DIR/.inkspire.new"
    chmod 755 "$BIN_DIR/.inkspire.new"
    mv -f "$BIN_DIR/.inkspire.new" "$BIN_DIR/inkspire"

    if [ -f "$TMP/inkspire.png" ]; then
        cp "$TMP/inkspire.png" "$ICON_FILE"
    fi

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Inkspire
Comment=Trace line art by moving the mouse along extracted contours
Exec="$BIN_DIR/inkspire"
Icon=inkspire
Terminal=false
Categories=Graphics;
StartupWMClass=Inkspire
EOF

    refresh_desktop_caches

    say "Installed Inkspire to $BIN_DIR/inkspire and added it to the app menu."

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) say "$BIN_DIR is not on your PATH, so start Inkspire from the app menu or add that folder to PATH." ;;
    esac

    if ! { ldconfig -p 2>/dev/null || /sbin/ldconfig -p 2>/dev/null; } | grep -q 'libXtst\.so\.6'; then
        say "libXtst is missing, and Inkspire needs it to move the pointer. Install libxtst6 (Debian, Ubuntu) or libXtst (Fedora, Arch)."
    fi
}

uninstall_linux() {
    rm -f "$BIN_DIR/inkspire" "$DESKTOP_FILE" "$ICON_FILE"
    refresh_desktop_caches

    say "Removed Inkspire. Settings in ~/.config/inkspire are kept; delete that folder to remove them too."
}

install_macos() {
    if [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = 1 ]; then
        ASSET=inkspire-macos-arm64.dmg
        MIN_MAJOR=13
    else
        ASSET=inkspire-macos-x86_64.dmg
        MIN_MAJOR=14
    fi

    OS_VERSION="$(sw_vers -productVersion)"
    [ "${OS_VERSION%%.*}" -ge "$MIN_MAJOR" ] || die "this build needs macOS $MIN_MAJOR or newer, found $OS_VERSION"

    if pgrep -x Inkspire >/dev/null 2>&1; then
        die "quit Inkspire first, then run the installer again"
    fi

    if [ -w /Applications ]; then
        APPS=/Applications
    else
        APPS="$HOME/Applications"
        mkdir -p "$APPS"
    fi

    TMP="$(mktemp -d)"
    MOUNT="$TMP/mount"
    # Detach before deleting, so cleanup never reaches into the mounted image.
    trap 'hdiutil detach -quiet "$MOUNT" 2>/dev/null || true; rm -f "$TMP/inkspire.dmg"; rmdir "$MOUNT" "$TMP" 2>/dev/null || true' EXIT

    download "$BASE/$ASSET" "$TMP/inkspire.dmg" || die "download failed: $BASE/$ASSET"
    mkdir "$MOUNT"
    hdiutil attach -quiet -nobrowse -readonly -mountpoint "$MOUNT" "$TMP/inkspire.dmg"

    UPDATE=false
    [ -d "$APPS/Inkspire.app" ] && UPDATE=true

    rm -rf "$APPS/Inkspire.app"
    ditto "$MOUNT/Inkspire.app" "$APPS/Inkspire.app"
    xattr -dr com.apple.quarantine "$APPS/Inkspire.app" 2>/dev/null || true

    say "Installed Inkspire to $APPS/Inkspire.app."

    # Each release has a new ad-hoc signature, so the Accessibility grant of the previous version no longer applies.
    if $UPDATE; then
        if tccutil reset Accessibility "$BUNDLE_ID" >/dev/null 2>&1; then
            say "Inkspire asks for Accessibility access again on its next launch, because the update changed its signature."
        else
            say "If drawing does nothing after this update, remove Inkspire under System Settings > Privacy & Security > Accessibility and add it again."
        fi
    fi
}

uninstall_macos() {
    rm -rf /Applications/Inkspire.app "$HOME/Applications/Inkspire.app"
    tccutil reset Accessibility "$BUNDLE_ID" >/dev/null 2>&1 || true

    say "Removed Inkspire. Settings in ~/.config/inkspire are kept; delete that folder to remove them too."
}

ACTION=install

for arg in "$@"; do
    case "$arg" in
        --uninstall) ACTION=uninstall ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $arg" ;;
    esac
done

case "$(uname -s)" in
    Linux) "${ACTION}_linux" ;;
    Darwin) "${ACTION}_macos" ;;
    *) die "this script supports Linux and macOS; on Windows use install.ps1 from https://github.com/$REPO#install" ;;
esac

#!/usr/bin/env bash
# Usage: packaging/make_dmg.sh dist/Inkspire.app dist/inkspire-macos-arm64.dmg
set -euo pipefail

APP="$1"
DMG="$2"
STAGE="$(mktemp -d)"

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname Inkspire -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG"
rm -rf "$STAGE"

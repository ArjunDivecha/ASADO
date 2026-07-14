#!/bin/bash
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
APP_NAME="ASADO Cockpit"
BUILD_DIR="$REPO/build/macos"
APP="$BUILD_DIR/$APP_NAME.app"
DEST="/Applications/$APP_NAME.app"
ICON_SVG="$REPO/scripts/macos/ASADO-Cockpit-icon.svg"
ICONSET="$BUILD_DIR/AppIcon.iconset"

rm -rf "$APP" "$ICONSET"
mkdir -p "$BUILD_DIR" "$ICONSET"
osacompile -s -o "$APP" "$REPO/scripts/macos/ASADO-Cockpit.applescript"
cp "$REPO/scripts/macos/asado-cockpit-launcher.sh" "$APP/Contents/Resources/asado-cockpit-server.sh"
chmod 755 "$APP/Contents/Resources/asado-cockpit-server.sh"

/usr/libexec/PlistBuddy -c 'Set :CFBundleName ASADO Cockpit' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName ASADO Cockpit' "$APP/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string ASADO Cockpit' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIdentifier com.arjundivecha.asado-cockpit' "$APP/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string com.arjundivecha.asado-cockpit' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleVersion 1.1.1' "$APP/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Add :CFBundleVersion string 1.1.1' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleShortVersionString 1.1.1' "$APP/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c 'Add :CFBundleShortVersionString string 1.1.1' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleIconFile AppIcon.icns' "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Delete :CFBundleIconName' "$APP/Contents/Info.plist" 2>/dev/null || true

# Quick Look renders the SVG reliably on stock macOS; sips creates every icon size.
mkdir -p "$BUILD_DIR/render"
rm -f "$BUILD_DIR/render/ASADO-Cockpit-icon.svg.png"
qlmanage -t -s 1024 -o "$BUILD_DIR/render" "$ICON_SVG" >/dev/null 2>&1
SOURCE_PNG="$BUILD_DIR/render/ASADO-Cockpit-icon.svg.png"
test -f "$SOURCE_PNG"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$SOURCE_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$SOURCE_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
# AppleScript applets have a legacy hard-wired applet.icns lookup path. Keep it
# aligned with CFBundleIconFile so neither path falls back to the scroll icon.
cp "$APP/Contents/Resources/AppIcon.icns" "$APP/Contents/Resources/applet.icns"

plutil -lint "$APP/Contents/Info.plist" >/dev/null
codesign --force --deep --sign - "$APP" >/dev/null
rm -rf "$DEST"
ditto "$APP" "$DEST"
touch "$DEST"

printf '%s\n' "$DEST"

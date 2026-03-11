#!/usr/bin/env bash
# Build VoiceText.app with PyInstaller and re-sign for macOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"
APP_PATH="$DIST_DIR/VoiceText.app"
SIGN_IDENTITY="${CODESIGN_IDENTITY:-VoiceText Dev}"

cd "$PROJECT_DIR"

echo "==> Cleaning previous build..."
rm -rf build dist

echo "==> Running PyInstaller..."
uv run pyinstaller VoiceText.spec --clean --noconfirm

echo "==> Re-signing app bundle (identity: $SIGN_IDENTITY)..."
codesign --force --deep --sign "$SIGN_IDENTITY" "$APP_PATH"

echo "==> Verifying signature..."
codesign --verify --verbose "$APP_PATH"

APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
echo ""
echo "==> Build complete: $APP_PATH ($APP_SIZE)"
echo "    Run with: open $APP_PATH"

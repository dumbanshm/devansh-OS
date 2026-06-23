#!/usr/bin/env bash
# Build the native macOS app: dist/Devansh OS.app
# Run from an activated venv with the project installed.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ building stylesheet"
bash scripts/build_css.sh

echo "→ installing build deps"
pip install -q -r requirements.txt -r requirements-desktop.txt

echo "→ packaging with PyInstaller"
pyinstaller --noconfirm packaging/DevanshOS.spec

# Seed the user data dir so the app keeps your existing config + history.
APPSUP="$HOME/Library/Application Support/DevanshOS"
mkdir -p "$APPSUP/data"
if [ ! -f "$APPSUP/.env" ] && [ -f .env ]; then
  cp .env "$APPSUP/.env"; echo "  · copied .env → $APPSUP"
fi
if [ ! -f "$APPSUP/data/devansh.db" ] && [ -f data/devansh.db ]; then
  cp data/devansh.db "$APPSUP/data/"; echo "  · copied database → $APPSUP/data"
fi
if [ -d data/hevy ] && [ ! -e "$APPSUP/data/hevy" ]; then
  cp -R data/hevy "$APPSUP/data/"; echo "  · copied Hevy CSV → $APPSUP/data/hevy"
fi

echo
echo "✓ Built: dist/Devansh OS.app"
echo "  Drag it to /Applications, then launch from Spotlight."
echo "  It appears in the menu bar (◐) and opens a window; enable 'Launch at Login' from its menu."

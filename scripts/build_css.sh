#!/usr/bin/env bash
# Build web/static/app.css from web/src/input.css.
# Prefers the Tailwind standalone binary (no Node needed); falls back to npx.
set -euo pipefail
cd "$(dirname "$0")/.."

IN="web/src/input.css"
OUT="web/static/app.css"
CFG="tailwind.config.js"

if command -v tailwindcss >/dev/null 2>&1; then
  echo "→ building with standalone tailwindcss"
  tailwindcss -c "$CFG" -i "$IN" -o "$OUT" --minify
elif command -v npx >/dev/null 2>&1; then
  echo "→ building with npx tailwindcss"
  npx --yes tailwindcss@3.4.17 -c "$CFG" -i "$IN" -o "$OUT" --minify
else
  echo "✗ Neither 'tailwindcss' (standalone) nor 'npx' found." >&2
  echo "  Install the standalone CLI from:" >&2
  echo "  https://github.com/tailwindlabs/tailwindcss/releases/latest" >&2
  exit 1
fi
echo "✓ wrote $OUT"

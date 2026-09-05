#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/generate_icons.py"
if command -v iconutil >/dev/null; then
  iconutil -c icns "$ROOT/src-tauri/icons/icon.iconset" -o "$ROOT/src-tauri/icons/icon.icns"
fi
cd "$ROOT/engine"
uv sync --extra dev
cd "$ROOT/ui"
npm install
npm run build
if command -v cargo >/dev/null; then
  if cargo tauri --version >/dev/null 2>&1; then
    cd "$ROOT/src-tauri"
    cargo tauri build
  else
    echo "Tauri CLI yok. Yüklemek için: cargo install tauri-cli --version '^2'"
    echo "Kaynaklar hazır; cargo check ile native kabuk doğrulanabilir:"
    cd "$ROOT/src-tauri"
    cargo check
  fi
fi

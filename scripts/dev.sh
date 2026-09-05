#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CVENGINE_DATA_DIR="${CVENGINE_DATA_DIR:-$HOME/Library/Application Support/CVENGINE}"

# Keep autostart runtime copy updated while developing from this tree.
if [[ -x "$ROOT/scripts/sync-runtime.sh" ]]; then
  "$ROOT/scripts/sync-runtime.sh" "$ROOT" >/dev/null 2>&1 || true
fi
WATCH="${CVENGINE_DATA_DIR}/bin/sync-runtime-watch.sh"
WATCH_PID_FILE="${CVENGINE_DATA_DIR}/run/sync-watch.pid"
start_watch() {
  local w="$1"
  if [[ -f "$WATCH_PID_FILE" ]] && kill -0 "$(cat "$WATCH_PID_FILE")" 2>/dev/null; then
    return 0
  fi
  mkdir -p "${CVENGINE_DATA_DIR}/logs"
  nohup /bin/bash "$w" >>"${CVENGINE_DATA_DIR}/logs/sync.log" 2>&1 &
  disown 2>/dev/null || true
}
if [[ -x "$WATCH" ]]; then
  start_watch "$WATCH"
elif [[ -x "$ROOT/scripts/sync-runtime-watch.sh" ]]; then
  mkdir -p "${CVENGINE_DATA_DIR}/bin"
  cp -f "$ROOT/scripts/sync-runtime.sh" "$ROOT/scripts/sync-runtime-watch.sh" "${CVENGINE_DATA_DIR}/bin/"
  chmod +x "${CVENGINE_DATA_DIR}/bin/"*.sh
  start_watch "${CVENGINE_DATA_DIR}/bin/sync-runtime-watch.sh"
fi

cleanup() {
  if [[ -n "${ENGINE_PID:-}" ]]; then kill "$ENGINE_PID" 2>/dev/null || true; fi
  if [[ -n "${UI_PID:-}" ]]; then kill "$UI_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

cd "$ROOT/engine"
uv sync --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload &
ENGINE_PID=$!

cd "$ROOT/ui"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev &
UI_PID=$!

echo "CVENGINE"
echo "  API  http://127.0.0.1:8765/api/health"
echo "  UI   http://127.0.0.1:5173"
wait

#!/usr/bin/env bash
set -euo pipefail
DATA="${CVENGINE_DATA_DIR:-$HOME/Library/Application Support/CVENGINE}"
PID_DIR="$DATA/run"

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
  fi
}

if [[ -f "$PID_DIR/engine.pid" ]]; then
  kill "$(cat "$PID_DIR/engine.pid")" 2>/dev/null || true
  rm -f "$PID_DIR/engine.pid"
fi
if [[ -f "$PID_DIR/ui.pid" ]]; then
  kill "$(cat "$PID_DIR/ui.pid")" 2>/dev/null || true
  rm -f "$PID_DIR/ui.pid"
fi
# Leave sync-watch running so the runtime copy keeps updating; use
# CVENGINE_STOP_SYNC=1 to stop it as well.
if [[ "${CVENGINE_STOP_SYNC:-}" == "1" && -f "$PID_DIR/sync-watch.pid" ]]; then
  kill "$(cat "$PID_DIR/sync-watch.pid")" 2>/dev/null || true
  rm -f "$PID_DIR/sync-watch.pid"
fi
stop_port 8765
stop_port 5173
echo "CVENGINE stopped"

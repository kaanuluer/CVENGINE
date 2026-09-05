#!/usr/bin/env bash
# Durable local start for CVENGINE (API + UI). Suitable for LaunchAgent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CVENGINE_DATA_DIR="${CVENGINE_DATA_DIR:-$HOME/Library/Application Support/CVENGINE}"
LOG_DIR="${CVENGINE_DATA_DIR}/logs"
PID_DIR="${CVENGINE_DATA_DIR}/run"
mkdir -p "$LOG_DIR" "$PID_DIR" "$CVENGINE_DATA_DIR"

# LaunchAgents have a minimal PATH — pin toolchain locations.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.nvm/versions/node/v20.19.6/bin:/usr/bin:/bin:$PATH"
UV_BIN="$(command -v uv)"
NPM_BIN="$(command -v npm)"
if [[ -z "$UV_BIN" || -z "$NPM_BIN" ]]; then
  echo "uv or npm not found in PATH=$PATH" >&2
  exit 1
fi

# Keep autostart runtime in sync when this checkout is the editable source.
RUNTIME_DIR="${CVENGINE_DATA_DIR}/runtime"
SOURCE_FILE="${CVENGINE_DATA_DIR}/source_path"
if [[ "$ROOT" != "$RUNTIME_DIR" ]]; then
  if [[ -x "$ROOT/scripts/sync-runtime.sh" ]]; then
    "$ROOT/scripts/sync-runtime.sh" "$ROOT" >/dev/null 2>&1 || true
  fi
elif [[ -f "$SOURCE_FILE" ]]; then
  src="$(cat "$SOURCE_FILE")"
  if [[ -r "$src/scripts/sync-runtime.sh" ]]; then
    "$src/scripts/sync-runtime.sh" "$src" >/dev/null 2>&1 || true
  fi
fi
# Ensure background watcher is running (no-op if already up)
WATCH="${CVENGINE_DATA_DIR}/bin/sync-runtime-watch.sh"
WATCH_PID_FILE="${CVENGINE_DATA_DIR}/run/sync-watch.pid"
if [[ -x "$WATCH" ]]; then
  if [[ -f "$WATCH_PID_FILE" ]] && kill -0 "$(cat "$WATCH_PID_FILE")" 2>/dev/null; then
    :
  else
    nohup /bin/bash "$WATCH" >>"${CVENGINE_DATA_DIR}/logs/sync.log" 2>&1 &
    disown 2>/dev/null || true
  fi
fi

ENGINE_LOG="$LOG_DIR/engine.log"
UI_LOG="$LOG_DIR/ui.log"

stop_if_running() {
  local port="$1"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.4
  fi
}

stop_if_running 8765
stop_if_running 5173

{
  echo "---- $(date -Iseconds) starting engine ----"
  cd "$ROOT/engine"
  if [[ ! -d .venv ]]; then
    "$UV_BIN" sync --extra dev
  fi
  nohup "$UV_BIN" run uvicorn app.main:app --host 127.0.0.1 --port 8765 >>"$ENGINE_LOG" 2>&1 &
  echo $! >"$PID_DIR/engine.pid"
} >>"$ENGINE_LOG" 2>&1

{
  echo "---- $(date -Iseconds) starting ui ----"
  cd "$ROOT/ui"
  if [[ ! -d node_modules ]]; then
    "$NPM_BIN" install
  fi
  nohup "$NPM_BIN" run dev -- --host 127.0.0.1 --port 5173 >>"$UI_LOG" 2>&1 &
  echo $! >"$PID_DIR/ui.pid"
} >>"$UI_LOG" 2>&1

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "CVENGINE started at $(date -Iseconds)"
echo "  API  http://127.0.0.1:8765/api/health"
echo "  UI   http://127.0.0.1:5173"
echo "  logs $LOG_DIR"

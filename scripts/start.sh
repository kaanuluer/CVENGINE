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

WATCH="${CVENGINE_DATA_DIR}/bin/sync-runtime-watch.sh"
WATCH_PID_FILE="${CVENGINE_DATA_DIR}/run/sync-watch.pid"
if [[ -x "$WATCH" ]]; then
  if [[ -f "$WATCH_PID_FILE" ]] && kill -0 "$(cat "$WATCH_PID_FILE")" 2>/dev/null; then
    :
  else
    "$ROOT/scripts/detach.py" --log "${CVENGINE_DATA_DIR}/logs/sync.log" -- \
      /bin/bash "$WATCH" >/dev/null 2>&1 || true
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

wait_port() {
  local port="$1"
  local i
  for i in $(seq 1 60); do
    if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

record_listen_pid() {
  local port="$1"
  local file="$2"
  local pid
  pid="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "$pid" ]]; then
    echo "$pid" >"$file"
  fi
}

stop_if_running 8765
stop_if_running 5173

echo "---- $(date -Iseconds) starting engine ----" >>"$ENGINE_LOG"
(
  cd "$ROOT/engine"
  if [[ ! -d .venv ]]; then
    "$UV_BIN" sync --extra dev >>"$ENGINE_LOG" 2>&1
  fi
)
# Double-fork so Cursor/agent shell teardown cannot kill the servers.
"$ROOT/scripts/detach.py" --chdir "$ROOT/engine" --log "$ENGINE_LOG" -- \
  "$UV_BIN" run uvicorn app.main:app --host 127.0.0.1 --port 8765

echo "---- $(date -Iseconds) starting ui ----" >>"$UI_LOG"
(
  cd "$ROOT/ui"
  if [[ ! -d node_modules ]]; then
    "$NPM_BIN" install >>"$UI_LOG" 2>&1
  fi
)
"$ROOT/scripts/detach.py" --chdir "$ROOT/ui" --log "$UI_LOG" -- \
  "$NPM_BIN" run dev -- --host 127.0.0.1 --port 5173

if ! wait_port 8765; then
  echo "Engine failed to bind :8765 — see $ENGINE_LOG" >&2
  exit 1
fi
if ! wait_port 5173; then
  echo "UI failed to bind :5173 — see $UI_LOG" >&2
  exit 1
fi

record_listen_pid 8765 "$PID_DIR/engine.pid"
record_listen_pid 5173 "$PID_DIR/ui.pid"

# Health check
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:8765/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

echo "CVENGINE started at $(date -Iseconds)"
echo "  API  http://127.0.0.1:8765/api/health"
echo "  UI   http://127.0.0.1:5173"
echo "  logs $LOG_DIR"

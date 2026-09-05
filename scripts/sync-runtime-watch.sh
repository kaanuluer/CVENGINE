#!/usr/bin/env bash
# Watch the editable source tree and keep the autostart runtime copy updated.
# Exclusive lock via mkdir (macOS has no flock(1) by default).
set +e
set +o pipefail 2>/dev/null || true
set -u

DATA="${CVENGINE_DATA_DIR:-$HOME/Library/Application Support/CVENGINE}"
SOURCE_FILE="$DATA/source_path"
PID_FILE="$DATA/run/sync-watch.pid"
LOCK_DIR="$DATA/run/sync-watch.lockdir"
LOG="$DATA/logs/sync.log"
RUNTIME="${CVENGINE_RUNTIME_DIR:-$DATA/runtime}"
SYNC_BIN="$DATA/bin/sync-runtime.sh"
mkdir -p "$DATA/logs" "$DATA/run" "$DATA/bin"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

log() { echo "$(date -Iseconds) $*" >>"$LOG"; }

resolve_sync() {
  if [[ -x "$SYNC_BIN" ]]; then
    printf '%s\n' "$SYNC_BIN"
  elif [[ -x "$(dirname "$0")/sync-runtime.sh" ]]; then
    printf '%s\n' "$(cd "$(dirname "$0")" && pwd)/sync-runtime.sh"
  else
    return 1
  fi
}

RSYNC_EXCLUDES=(
  --exclude '.git/'
  --exclude 'src-tauri/target/'
  --exclude 'ui/node_modules/'
  --exclude 'engine/.venv/'
  --exclude 'engine/.pytest_cache/'
  --exclude '**/__pycache__/'
  --exclude '.DS_Store'
)

can_rsync() {
  local src="$1"
  [[ -n "$src" && -d "$src" ]] || return 1
  rsync -ai --delete "${RSYNC_EXCLUDES[@]}" --dry-run "$src/" "$RUNTIME/" >/dev/null 2>&1
}

has_pending_changes() {
  local src="$1"
  local out
  out="$(rsync -ai --delete "${RSYNC_EXCLUDES[@]}" --dry-run "$src/" "$RUNTIME/" 2>/dev/null | head -n 1)"
  [[ -n "$out" ]]
}

do_sync() {
  local sync_sh src
  sync_sh="$(resolve_sync)" || return 1
  src="$(cat "$SOURCE_FILE" 2>/dev/null || true)"
  if ! can_rsync "$src"; then
    log "watch: cannot rsync source"
    return 1
  fi
  "$sync_sh" "$src" >>"$LOG" 2>&1
}

release_lock() {
  rm -f "$PID_FILE"
  rm -rf "$LOCK_DIR"
}

acquire_lock() {
  while true; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      echo $$ >"$LOCK_DIR/pid"
      return 0
    fi
    local old
    old="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ -n "${old:-}" ]] && kill -0 "$old" 2>/dev/null; then
      sleep 5
      continue
    fi
    rm -rf "$LOCK_DIR"
  done
}

src="$(cat "$SOURCE_FILE" 2>/dev/null || true)"
if ! can_rsync "${src:-}"; then
  log "watch: source not syncable yet (${src:-unset}); exit"
  sleep 5
  exit 1
fi

acquire_lock
echo $$ >"$PID_FILE"
trap 'log "watch exiting pid=$$"; release_lock' EXIT INT TERM

log "watch started pid=$$ source=$src"
do_sync

while true; do
  src="$(cat "$SOURCE_FILE" 2>/dev/null || true)"
  if ! can_rsync "${src:-}"; then
    log "watch: lost rsync access; exiting"
    exit 1
  fi
  if has_pending_changes "$src"; then
    sleep 1
    do_sync || log "watch: sync failed (will retry)"
  fi
  sleep 2
done

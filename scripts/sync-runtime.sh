#!/usr/bin/env bash
# Sync the editable source tree → Application Support runtime (autostart copy).
set -euo pipefail

DATA="${CVENGINE_DATA_DIR:-$HOME/Library/Application Support/CVENGINE}"
RUNTIME="${CVENGINE_RUNTIME_DIR:-$DATA/runtime}"
SOURCE_FILE="$DATA/source_path"
LOG="$DATA/logs/sync.log"
mkdir -p "$DATA/logs" "$RUNTIME" "$DATA/bin"

SOURCE="${1:-${CVENGINE_SOURCE:-}}"
if [[ -z "$SOURCE" && -f "$SOURCE_FILE" ]]; then
  SOURCE="$(cat "$SOURCE_FILE")"
fi
if [[ -z "$SOURCE" ]]; then
  # Infer: this script lives in <root>/scripts/
  HERE="$(cd "$(dirname "$0")/.." && pwd)"
  case "$HERE" in
    */Library/Application\ Support/CVENGINE/runtime) ;;
    *) SOURCE="$HERE" ;;
  esac
fi

if [[ -z "${SOURCE:-}" ]]; then
  echo "sync-runtime: no source path (set CVENGINE_SOURCE or pass as \$1)" >&2
  exit 1
fi
if [[ ! -d "$SOURCE" ]]; then
  echo "sync-runtime: source not readable: $SOURCE" >&2
  exit 1
fi
if [[ "$(cd "$SOURCE" && pwd)" == "$(cd "$RUNTIME" && pwd)" ]]; then
  echo "sync-runtime: refusing to sync runtime onto itself" >&2
  exit 1
fi

# Resolve absolute path and remember it for the watcher / LaunchAgent
SOURCE="$(cd "$SOURCE" && pwd)"
printf '%s\n' "$SOURCE" >"$SOURCE_FILE"

rsync -a --delete \
  --exclude '.git/' \
  --exclude 'src-tauri/target/' \
  --exclude 'ui/node_modules/' \
  --exclude 'engine/.venv/' \
  --exclude 'engine/.pytest_cache/' \
  --exclude '**/__pycache__/' \
  --exclude '.DS_Store' \
  "$SOURCE/" "$RUNTIME/"

# Keep helper scripts outside Desktop for LaunchAgents.
# Never overwrite sync-runtime-watch.sh while it is running (bash reads scripts
# incrementally; replacing the file mid-loop kills the watcher).
WATCH_PID_FILE="$DATA/run/sync-watch.pid"
watcher_running=0
if [[ -f "$WATCH_PID_FILE" ]] && kill -0 "$(cat "$WATCH_PID_FILE")" 2>/dev/null; then
  watcher_running=1
fi
for name in sync-runtime.sh sync-runtime-watch.sh start.sh stop.sh; do
  if [[ "$name" == "sync-runtime-watch.sh" && "$watcher_running" -eq 1 ]]; then
    continue
  fi
  if [[ -f "$RUNTIME/scripts/$name" ]]; then
    cp -f "$RUNTIME/scripts/$name" "$DATA/bin/$name"
    chmod +x "$DATA/bin/$name"
  fi
done
chmod +x "$RUNTIME/scripts/"*.sh "$RUNTIME/scripts/"*.command 2>/dev/null || true

{
  echo "$(date -Iseconds) synced $SOURCE → $RUNTIME"
} >>"$LOG"

echo "Synced → $RUNTIME"

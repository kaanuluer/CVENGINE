#!/usr/bin/env bash
# Install CVENGINE so it starts at every login, and keep the runtime copy
# auto-synced when the editable source tree changes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$HOME/Library/Application Support/CVENGINE"
RUNTIME="$DATA/runtime"
PLIST_DST="$HOME/Library/LaunchAgents/com.cvengine.app.plist"
SYNC_PLIST_DST="$HOME/Library/LaunchAgents/com.cvengine.sync.plist"
UID_NUM="$(id -u)"

chmod +x "$ROOT/scripts/"*.sh "$ROOT/scripts/"*.command 2>/dev/null || true
mkdir -p "$RUNTIME" "$DATA/logs" "$DATA/run" "$DATA/bin" "$HOME/Library/LaunchAgents" "$HOME/Applications"

# Initial sync + remember source path
"$ROOT/scripts/sync-runtime.sh" "$ROOT"

UV_BIN="$(command -v uv || true)"
NPM_BIN="$(command -v npm || true)"
NODE_DIR=""
if [[ -n "$NPM_BIN" ]]; then
  NODE_DIR="$(cd "$(dirname "$NPM_BIN")" && pwd)"
fi
PATH_VALUE="/opt/homebrew/bin:/usr/local/bin:${NODE_DIR}:/usr/bin:/bin:/usr/sbin:/sbin"
if [[ -z "$UV_BIN" || -z "$NPM_BIN" ]]; then
  echo "warning: uv or npm not found now; LaunchAgent will use PATH=$PATH_VALUE" >&2
fi

APP="$HOME/Applications/CVENGINE.app"
mkdir -p "$APP/Contents/MacOS"
cat >"$APP/Contents/MacOS/CVENGINE" <<EOF
#!/bin/bash
exec "$RUNTIME/scripts/start.sh"
EOF
chmod +x "$APP/Contents/MacOS/CVENGINE"
cat >"$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>CVENGINE</string>
  <key>CFBundleIdentifier</key>
  <string>com.cvengine.app</string>
  <key>CFBundleName</key>
  <string>CVENGINE</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSUIElement</key>
  <true/>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
</dict>
</plist>
PLIST

# Sync.app: LaunchAgent opens this at login. Grant Desktop access once if prompted.
SYNC_APP="$HOME/Applications/CVENGINE Sync.app"
mkdir -p "$SYNC_APP/Contents/MacOS"
cat >"$SYNC_APP/Contents/MacOS/CVENGINE Sync" <<EOF
#!/bin/bash
export CVENGINE_DATA_DIR="$DATA"
export PATH="$PATH_VALUE"
exec /bin/bash "$DATA/bin/sync-runtime-watch.sh"
EOF
chmod +x "$SYNC_APP/Contents/MacOS/CVENGINE Sync"
cat >"$SYNC_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>CVENGINE Sync</string>
  <key>CFBundleIdentifier</key>
  <string>com.cvengine.sync</string>
  <key>CFBundleName</key>
  <string>CVENGINE Sync</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSUIElement</key>
  <true/>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
</dict>
</plist>
PLIST

cat >"$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.cvengine.app</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNTIME/scripts/start.sh</string>
  </array>
  <key>AbandonProcessGroup</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>WorkingDirectory</key>
  <string>$RUNTIME</string>
  <key>StandardOutPath</key>
  <string>$DATA/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$DATA/logs/launchd.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>$HOME</string>
    <key>PATH</key>
    <string>$PATH_VALUE</string>
    <key>CVENGINE_DATA_DIR</key>
    <string>$DATA</string>
  </dict>
</dict>
</plist>
EOF

cat >"$SYNC_PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.cvengine.sync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>-gj</string>
    <string>$SYNC_APP</string>
  </array>
  <key>AbandonProcessGroup</key>
  <true/>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$DATA/logs/sync-launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$DATA/logs/sync-launchd.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>$HOME</string>
  </dict>
</dict>
</plist>
EOF

cp "$PLIST_DST" "$ROOT/scripts/com.cvengine.app.plist"

if [[ -d "$ROOT/.git" ]]; then
  mkdir -p "$ROOT/.git/hooks"
  for hook in post-commit post-merge post-checkout; do
    cat >"$ROOT/.git/hooks/$hook" <<EOF
#!/bin/bash
"$ROOT/scripts/sync-runtime.sh" "$ROOT" >/dev/null 2>&1 || true
EOF
    chmod +x "$ROOT/.git/hooks/$hook"
  done
fi

: >"$DATA/logs/launchd.err.log"
: >"$DATA/logs/launchd.out.log"

launchctl bootout "gui/${UID_NUM}/com.cvengine.app" 2>/dev/null || true
launchctl bootout "gui/${UID_NUM}/com.cvengine.sync" 2>/dev/null || true
launchctl bootout "gui/${UID_NUM}/com.cvengine.sync-watchpaths" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.cvengine.sync-watchpaths.plist"

# Stop previous watchers cleanly, then install fresh bin scripts
pkill -f sync-runtime-watch.sh 2>/dev/null || true
sleep 0.5
rm -rf "$DATA/run/sync-watch.lockdir"
rm -f "$DATA/run/sync-watch.pid"
cp -f "$ROOT/scripts/sync-runtime.sh" "$ROOT/scripts/sync-runtime-watch.sh" "$DATA/bin/"
chmod +x "$DATA/bin/"*.sh

launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DST"
launchctl bootstrap "gui/${UID_NUM}" "$SYNC_PLIST_DST"
launchctl enable "gui/${UID_NUM}/com.cvengine.app" 2>/dev/null || true
launchctl enable "gui/${UID_NUM}/com.cvengine.sync" 2>/dev/null || true

# Interactive watcher (has Desktop access in this session)
nohup /bin/bash "$DATA/bin/sync-runtime-watch.sh" >>"$DATA/logs/sync.log" 2>&1 &
disown || true
open -gj "$SYNC_APP" 2>/dev/null || true

for _ in $(seq 1 30); do
  if [[ -f "$DATA/run/sync-watch.pid" ]] && kill -0 "$(cat "$DATA/run/sync-watch.pid")" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

echo
echo "Autostart + auto-sync ready."
echo "  Source:       $ROOT"
echo "  Runtime copy: $RUNTIME"
echo "  Watcher pid:  $(cat "$DATA/run/sync-watch.pid" 2>/dev/null || echo '(not running)')"
echo "  Sync app:     $SYNC_APP"
echo
echo "Kod değişince runtime kopyası ~2sn içinde güncellenir."
echo "macOS Desktop erişimi isterse \"CVENGINE Sync\" için İzin Ver."
echo
echo "Disable:"
echo "  launchctl bootout gui/\$(id -u)/com.cvengine.app"
echo "  launchctl bootout gui/\$(id -u)/com.cvengine.sync"
echo "  pkill -f sync-runtime-watch.sh"
echo "  rm -f \"$PLIST_DST\" \"$SYNC_PLIST_DST\""

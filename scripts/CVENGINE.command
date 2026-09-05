#!/bin/bash
# Double-clickable / Login Item entry point for CVENGINE
cd "$(dirname "$0")/.." || exit 1
./scripts/start.sh
sleep 2
open "http://127.0.0.1:5173/" >/dev/null 2>&1 || true

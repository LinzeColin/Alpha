#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/runtime/alpha_dashboard.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Alpha dashboard is not running."
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped Alpha dashboard process $PID."
else
  echo "Alpha dashboard process $PID is not active."
fi
rm -f "$PID_FILE"

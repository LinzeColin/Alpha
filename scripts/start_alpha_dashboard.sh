#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p runtime

PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_PY=".venv/bin/python"
PID_FILE="runtime/alpha_dashboard.pid"
LOG_FILE="runtime/alpha_dashboard.log"
URL="http://127.0.0.1:8000/dashboard"

if [[ ! -x "$APP_PY" ]]; then
  "$PYTHON_BIN" -m venv .venv
  "$APP_PY" -m pip install -e .
fi

OPEN_BROWSER="${ALPHA_OPEN_BROWSER:-1}"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Alpha dashboard already running at $URL"
    if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
      open "$URL"
    fi
    exit 0
  fi
fi

nohup "$APP_PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >"$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"

echo "Alpha dashboard started at $URL"
echo "Log: $ROOT/$LOG_FILE"

if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi

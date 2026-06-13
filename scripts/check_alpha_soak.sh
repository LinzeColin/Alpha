#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_PY=".venv/bin/python"

if [[ ! -x "$APP_PY" ]]; then
  "$PYTHON_BIN" -m venv .venv
  "$APP_PY" -m pip install -e .
fi

API_URL="${ALPHA_SOAK_API_URL:-http://127.0.0.1:8000/readiness/soak}"

if curl -fsS "$API_URL" >/dev/null 2>&1; then
  "$APP_PY" -m backend.app.services.soak_readiness --api-url "$API_URL" "$@"
else
  "$APP_PY" -m backend.app.services.soak_readiness "$@"
fi

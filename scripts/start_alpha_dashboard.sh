#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p runtime

PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_PY=".venv/bin/python"
DASHBOARD_PID_FILE="runtime/alpha_dashboard.pid"
DASHBOARD_LOG_FILE="runtime/alpha_dashboard.log"
URL="http://127.0.0.1:8000/dashboard"

if [[ ! -x "$APP_PY" ]]; then
  "$PYTHON_BIN" -m venv .venv
  "$APP_PY" -m pip install -e .
fi

OPEN_BROWSER="${ALPHA_OPEN_BROWSER:-1}"

if [[ -f "$DASHBOARD_PID_FILE" ]]; then
  PID="$(cat "$DASHBOARD_PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Alpha 控制台已在 $URL 运行。"
    if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
      open "$URL"
    fi
    exit 0
  else
    rm -f "$DASHBOARD_PID_FILE"
  fi
fi

if HEALTH="$(curl -fsS "http://127.0.0.1:8000/health" 2>/dev/null)" && [[ "$HEALTH" == *"research_paper_order_intent_review"* ]]; then
  if command -v lsof >/dev/null 2>&1; then
    EXISTING_PID="$(lsof -tiTCP:8000 -sTCP:LISTEN | head -n 1 || true)"
    if [[ -n "$EXISTING_PID" ]]; then
      echo "$EXISTING_PID" > "$DASHBOARD_PID_FILE"
      echo "Alpha 控制台已在 $URL 运行，进程号 $EXISTING_PID。"
    else
      echo "Alpha 控制台已在 $URL 运行。"
    fi
  else
    echo "Alpha 控制台已在 $URL 运行。"
  fi
  if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
    open "$URL"
  fi
  exit 0
fi

nohup "$APP_PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >"$DASHBOARD_LOG_FILE" 2>&1 &
echo "$!" > "$DASHBOARD_PID_FILE"

echo "Alpha 控制台已启动：$URL"
echo "Alpha 模拟交易智能体循环由控制台应用运行时托管。"
echo "控制台日志：$ROOT/$DASHBOARD_LOG_FILE"

READY=0
for _ in {1..60}; do
  if ! kill -0 "$(cat "$DASHBOARD_PID_FILE")" 2>/dev/null; then
    echo "Alpha 控制台启动期间失败。"
    tail -n 80 "$DASHBOARD_LOG_FILE" || true
    rm -f "$DASHBOARD_PID_FILE"
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "Alpha 控制台健康检查通过。"
    READY=1
    break
  fi
  sleep 0.5
done

if [[ "$READY" != "1" ]]; then
  echo "Alpha 控制台 30 秒内未就绪。"
  tail -n 80 "$DASHBOARD_LOG_FILE" || true
  rm -f "$DASHBOARD_PID_FILE"
  exit 1
fi

if [[ "$OPEN_BROWSER" != "0" ]] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi

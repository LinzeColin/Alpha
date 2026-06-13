#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_PID_FILE="$ROOT/runtime/alpha_dashboard.pid"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "Alpha ${name} 未运行。"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "已停止 Alpha ${name} 进程 ${pid}。"
        rm -f "$pid_file"
        return
      fi
      sleep 0.25
    done
    echo "Alpha ${name} 进程 ${pid} 仍在关闭中。"
  else
    echo "Alpha ${name} 进程 ${pid} 未处于活动状态。"
  fi
  rm -f "$pid_file"
}

stop_pid_file "控制台" "$DASHBOARD_PID_FILE"

if command -v lsof >/dev/null 2>&1; then
  while read -r listener_pid; do
    [[ -z "$listener_pid" ]] && continue
    command_line="$(ps -p "$listener_pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" == *"uvicorn backend.app.main:app"* ]]; then
      kill "$listener_pid" 2>/dev/null || true
      echo "已停止 Alpha 控制台监听进程 ${listener_pid}。"
    fi
  done < <(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)
fi

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_PID_FILE="$ROOT/runtime/alpha_dashboard.pid"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "Alpha $name is not running."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    for _ in {1..20}; do
      if ! kill -0 "$pid" 2>/dev/null; then
        echo "Stopped Alpha $name process $pid."
        rm -f "$pid_file"
        return
      fi
      sleep 0.25
    done
    echo "Alpha $name process $pid is still shutting down."
  else
    echo "Alpha $name process $pid is not active."
  fi
  rm -f "$pid_file"
}

stop_pid_file "dashboard" "$DASHBOARD_PID_FILE"

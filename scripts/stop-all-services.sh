#!/usr/bin/env bash
# Stops services started by start-all-services.sh, using their recorded PIDs only.
source "$(dirname "$0")/_common.sh"
shopt -s nullglob
for f in "$RUN_DIR"/*.pid; do
  svc="$(basename "$f" .pid)"; pid="$(cat "$f")"
  if ps -p "$pid" -o command= 2>/dev/null | grep -q "uvicorn app.main:app"; then
    kill "$pid" && echo "stopped $svc (pid $pid)"
  else
    echo "skip $svc: pid $pid is not running (or is not our uvicorn)"
  fi
  rm -f "$f"
done

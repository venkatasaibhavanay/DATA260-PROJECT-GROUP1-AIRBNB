#!/usr/bin/env bash
# Starts all six services in the background. Logs: .run/logs/<service>.log
# Stop them with ./scripts/stop-all-services.sh (only stops processes this script started).
source "$(dirname "$0")/_common.sh"
load_env; require_venv
mkdir -p "$RUN_DIR/logs"
for svc in "${SERVICES[@]}"; do
  port="$(port_for "$svc")"; owner="$(port_owner "$port")"
  if [ -n "$owner" ]; then echo "SKIP  $svc: port $port in use by $owner"; continue; fi
  ( cd "$ROOT/backend/$svc" && PYTHONPATH="$ROOT/backend/$svc:$ROOT" \
      nohup "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$port" \
      > "$RUN_DIR/logs/$svc.log" 2>&1 & echo $! > "$RUN_DIR/$svc.pid" )
  echo "START $svc on :$port (pid $(cat "$RUN_DIR/$svc.pid"))"
done
echo "Run ./scripts/health-check.sh in a few seconds."

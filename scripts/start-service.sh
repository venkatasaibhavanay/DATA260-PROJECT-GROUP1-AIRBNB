#!/usr/bin/env bash
# Starts one FastAPI service in the foreground with auto-reload.
# Usage: ./scripts/start-service.sh booking-service   (or: booking)
source "$(dirname "$0")/_common.sh"
[ $# -ge 1 ] || { echo "Usage: $0 <service>   (${SERVICES[*]})" >&2; exit 1; }
load_env; require_venv
svc="$(resolve_service "$1")"; port="$(port_for "$svc")"
owner="$(port_owner "$port")"
[ -z "$owner" ] || { echo "ERROR: port $port is already in use by $owner. Not starting." >&2; exit 1; }
cd "$ROOT/backend/$svc"
export PYTHONPATH="$ROOT/backend/$svc:$ROOT"
echo "Starting $svc on http://localhost:$port  (Swagger: http://localhost:$port/docs)"
exec "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$port" --reload \
  --reload-dir "$ROOT/backend/$svc" --reload-dir "$ROOT/shared"

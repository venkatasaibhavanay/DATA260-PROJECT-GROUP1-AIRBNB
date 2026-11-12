#!/usr/bin/env bash
# Shared helpers sourced by the other scripts. Not meant to be run directly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
RUN_DIR="$ROOT/.run"

# Pick up common user-level / Homebrew tool locations if they exist.
for d in "$HOME/.local/bin" "$HOME/.local/node/bin" /opt/homebrew/bin /usr/local/bin; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$d:$PATH";; esac
done
export PATH

SERVICES=(user-service property-service booking-service messaging-review-service ai-service analytics-service)

load_env() {
  if [ ! -f "$ROOT/.env" ]; then
    echo "ERROR: $ROOT/.env not found. Run ./scripts/setup-env.sh first." >&2
    exit 1
  fi
  set -a; . "$ROOT/.env"; set +a
}

# Accepts full names (booking-service) or short names (booking, bookings).
resolve_service() {
  case "$1" in
    user|users|user-service) echo user-service ;;
    property|properties|property-service) echo property-service ;;
    booking|bookings|booking-service) echo booking-service ;;
    messaging|reviews|messaging-review-service) echo messaging-review-service ;;
    ai|ai-service) echo ai-service ;;
    analytics|analytics-service) echo analytics-service ;;
    *) echo "Unknown service: $1 (valid: ${SERVICES[*]})" >&2; return 1 ;;
  esac
}

port_var_for() {
  case "$1" in
    user-service) echo USER_SERVICE_PORT ;;
    property-service) echo PROPERTY_SERVICE_PORT ;;
    booking-service) echo BOOKING_SERVICE_PORT ;;
    messaging-review-service) echo MESSAGING_REVIEW_SERVICE_PORT ;;
    ai-service) echo AI_SERVICE_PORT ;;
    analytics-service) echo ANALYTICS_SERVICE_PORT ;;
  esac
}

port_for() { local v; v="$(port_var_for "$1")"; echo "${!v}"; }

# Prints the process listening on a TCP port, or nothing if free.
port_owner() { lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR>1 {print $1" (pid "$2")"}' | sort -u | paste -sd, - || true; }

compose() {
  docker compose -f "$ROOT/infrastructure/docker-compose.yml" --env-file "$ROOT/.env" "$@"
}

require_venv() {
  if [ ! -x "$VENV/bin/python" ]; then
    echo "ERROR: Python environment missing. Run ./scripts/setup-python.sh first." >&2
    exit 1
  fi
}

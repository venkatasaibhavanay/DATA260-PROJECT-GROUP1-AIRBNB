#!/usr/bin/env bash
# Manage ONLY this project's Docker containers (Compose project data260-group1).
# Usage: ./scripts/infra.sh up | down | status | logs [service] | restart [service] | config
source "$(dirname "$0")/_common.sh"
load_env
docker info >/dev/null 2>&1 || { echo "ERROR: Docker is not running. Start Docker Desktop." >&2; exit 1; }
cmd="${1:-status}"; shift || true
case "$cmd" in
  up)      compose up -d "$@"; echo; compose ps ;;
  down)    compose down "$@"; echo "Stopped. Data volumes are kept." ;;
  status|ps) compose ps -a ;;
  logs)    compose logs -f --tail=100 "$@" ;;
  restart) compose restart "$@" ;;
  config)  compose config --quiet && echo "docker-compose.yml is valid." ;;
  *) echo "Usage: $0 up|down|status|logs [svc]|restart [svc]|config" >&2; exit 1 ;;
esac

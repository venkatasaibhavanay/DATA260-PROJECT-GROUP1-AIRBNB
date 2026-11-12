#!/usr/bin/env bash
# Reports whether required tools are installed. Changes nothing.
source "$(dirname "$0")/_common.sh"
set +e
fail=0
check() {
  local name="$1" cmd="$2"
  if out="$(eval "$cmd" 2>/dev/null | head -1)" && [ -n "$out" ]; then
    printf "  OK   %-16s %s\n" "$name" "$out"
  else
    printf "  MISS %-16s\n" "$name"; fail=1
  fi
}
echo "Prerequisites:"
check git            "git --version"
check python         "{ [ -x '$VENV/bin/python' ] && '$VENV/bin/python' --version; } || python3.12 --version || python3 --version"
check uv             "uv --version"
check node           "node --version"
check npm            "npm --version"
check docker         "docker --version"
check "docker compose" "docker compose version"
check gh             "gh --version"
if docker info >/dev/null 2>&1; then echo "  OK   docker engine    running"; else echo "  MISS docker engine    not running (start Docker Desktop)"; fail=1; fi
node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)"
[ -n "$node_major" ] && [ "$node_major" -lt 20 ] && { echo "  WARN Node $node_major is too old for Vite; use Node 22 LTS"; fail=1; }
[ -f "$ROOT/.env" ] && echo "  OK   .env present" || echo "  INFO .env missing — run ./scripts/setup-env.sh"
exit $fail

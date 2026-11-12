#!/usr/bin/env bash
# Calls GET /health on every service. Add --deps to also probe MySQL/MongoDB/Redis/Kafka.
source "$(dirname "$0")/_common.sh"
load_env
deps=0; [ "${1:-}" = "--deps" ] && deps=1
fail=0
for svc in "${SERVICES[@]}"; do
  port="$(port_for "$svc")"
  if body="$(curl -fsS -m 3 "http://localhost:$port/health" 2>/dev/null)"; then
    printf "  UP    %-26s :%s  %s\n" "$svc" "$port" "$body"
  else
    printf "  DOWN  %-26s :%s\n" "$svc" "$port"; fail=1; continue
  fi
  if [ $deps -eq 1 ]; then
    tmp="$(mktemp)"; code="$(curl -s -m 15 -o "$tmp" -w "%{http_code}" "http://localhost:$port/health/dependencies" || true)"
    printf "        dependencies HTTP %s  %s\n" "$code" "$(cat "$tmp")"; rm -f "$tmp"
    [ "$code" = "200" ] || fail=1
  fi
done
exit $fail

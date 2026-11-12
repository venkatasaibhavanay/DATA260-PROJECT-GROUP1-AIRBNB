#!/usr/bin/env bash
# Runs shared tests and each service's tests (each service in its own pytest run,
# because every service uses the package name "app").
# Usage: ./scripts/run-tests.sh [--integration] [service ...]
source "$(dirname "$0")/_common.sh"
require_venv
cd "$ROOT"
[ "${1:-}" = "--integration" ] && { export RUN_INTEGRATION=1; shift; }
targets=("$@"); [ ${#targets[@]} -gt 0 ] || targets=(shared "${SERVICES[@]}")
fail=0
for t in "${targets[@]}"; do
  if [ "$t" = shared ]; then
    echo "=== shared + integration tests (tests/) ==="
    "$VENV/bin/python" -m pytest -q tests || fail=1
  else
    svc="$(resolve_service "$t")"
    echo "=== $svc ==="
    ( cd "backend/$svc" && PYTHONPATH="$ROOT/backend/$svc:$ROOT" "$VENV/bin/python" -m pytest -q -p no:cacheprovider tests ) || fail=1
  fi
done
[ $fail -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit $fail

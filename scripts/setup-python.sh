#!/usr/bin/env bash
# Creates the shared project virtual environment at .venv and installs backend deps.
# Uses uv if available, otherwise python3.12 / python3.11 with venv + pip.
source "$(dirname "$0")/_common.sh"
cd "$ROOT"
if command -v uv >/dev/null 2>&1; then
  [ -x "$VENV/bin/python" ] || uv venv --python 3.12 "$VENV"
  uv pip install --python "$VENV/bin/python" -r backend/requirements-dev.txt
else
  PY=""
  for c in python3.13 python3.12 python3.11; do command -v "$c" >/dev/null && { PY="$c"; break; }; done
  [ -n "$PY" ] || { echo "ERROR: need Python 3.11+ (or uv). See README prerequisites." >&2; exit 1; }
  [ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install -r backend/requirements-dev.txt
fi
echo "Python environment ready: $("$VENV/bin/python" --version)"

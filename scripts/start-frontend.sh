#!/usr/bin/env bash
# Starts the React dev server on FRONTEND_PORT (5101). Fails if the port is taken.
source "$(dirname "$0")/_common.sh"
load_env
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
exec npm run dev

#!/usr/bin/env bash
# Creates .env from .env.example, replacing every "change_me" with a random local password.
# Never overwrites an existing .env.
source "$(dirname "$0")/_common.sh"
cd "$ROOT"
if [ -f .env ]; then
  echo ".env already exists — leaving it unchanged."
  exit 0
fi
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    *=change_me) echo "${line%%=*}=$(openssl rand -hex 16)" ;;
    *) echo "$line" ;;
  esac
done < .env.example > .env
chmod 600 .env
echo "Created .env with random local passwords (git-ignored, permissions 600)."

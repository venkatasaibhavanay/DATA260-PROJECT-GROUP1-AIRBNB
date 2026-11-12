#!/usr/bin/env bash
# Shows whether each Group 1 port is free. Never stops any process.
source "$(dirname "$0")/_common.sh"
[ -f "$ROOT/.env" ] && load_env
busy=0
printf "%-28s %-6s %s\n" "COMPONENT" "PORT" "STATUS"
while read -r name var def; do
  p="${!var:-$def}"
  owner="$(port_owner "$p")"
  if [ -z "$owner" ]; then status="free"; else status="IN USE by $owner"; busy=1; fi
  printf "%-28s %-6s %s\n" "$name" "$p" "$status"
done <<'LIST'
frontend FRONTEND_PORT 5101
user-service USER_SERVICE_PORT 8101
property-service PROPERTY_SERVICE_PORT 8111
booking-service BOOKING_SERVICE_PORT 8121
messaging-review-service MESSAGING_REVIEW_SERVICE_PORT 8131
ai-service AI_SERVICE_PORT 8141
analytics-service ANALYTICS_SERVICE_PORT 8151
mysql MYSQL_HOST_PORT 3311
mongodb MONGO_HOST_PORT 27101
redis REDIS_HOST_PORT 6381
kafka KAFKA_HOST_PORT 9091
LIST
echo
echo "\"IN USE\" is expected for components you have already started (python/node/com.docker)."
echo "If another app holds a port, choose a different free port ending in 1 and update .env."
exit 0

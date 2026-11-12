#!/usr/bin/env bash
# Creates every topic in $TOPICS_FILE plus its "<topic>.dlq" dead-letter topic.
# Idempotent (--if-not-exists). Runs inside the kafka-init container.
set -euo pipefail
BOOTSTRAP="${BOOTSTRAP:-kafka:29092}"
TOPICS_FILE="${TOPICS_FILE:-/config/topics.txt}"
KT=/opt/kafka/bin/kafka-topics.sh

while IFS= read -r topic || [ -n "$topic" ]; do
  topic="$(echo "$topic" | xargs)"
  [[ -z "$topic" || "$topic" == \#* ]] && continue
  for t in "$topic" "$topic.dlq"; do
    "$KT" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
      --topic "$t" --partitions 3 --replication-factor 1 > /dev/null
    echo "topic ready: $t"
  done
done < "$TOPICS_FILE"
echo "All Group 1 topics created."

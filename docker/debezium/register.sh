#!/bin/sh
# Registers (or updates) connector outbox-all, then waits until connector + task are RUNNING. POSIX sh (curl image).
set -eu
URL="${CONNECT_URL:-http://connect:8083}"
DIR="$(dirname "$0")"
i=0
until curl -fsS "$URL/connectors" >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 90 ] && { echo "connect not reachable at $URL" >&2; exit 1; }; sleep 2
done
curl -fsS -X PUT -H 'Content-Type: application/json' --data @"$DIR/outbox-all.json" \
  "$URL/connectors/outbox-all/config" >/dev/null
i=0
while :; do
  n="$(curl -fsS "$URL/connectors/outbox-all/status" 2>/dev/null | grep -o '"state":"RUNNING"' | wc -l | tr -d ' ')"
  [ "${n:-0}" -ge 2 ] && { echo "outbox-all RUNNING"; exit 0; }
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "outbox-all not RUNNING" >&2; curl -s "$URL/connectors/outbox-all/status" >&2; exit 1; }
  sleep 2
done

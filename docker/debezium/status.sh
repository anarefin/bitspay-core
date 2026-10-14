#!/bin/sh
# Prints the outbox-all status; exits non-zero unless connector and task are RUNNING.
set -eu
URL="${CONNECT_URL:-http://localhost:8083}"
s="$(curl -fsS "$URL/connectors/outbox-all/status" 2>/dev/null)" || { echo "outbox-all: connect unreachable or connector missing"; exit 1; }
echo "$s"
n="$(echo "$s" | grep -o '"state":"RUNNING"' | wc -l | tr -d ' ')"
[ "${n:-0}" -ge 2 ]

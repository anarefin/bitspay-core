#!/usr/bin/env bash
# Creates every topic from topics.csv (+ <topic>.dlq) and the Connect internal topics. Idempotent.
set -euo pipefail
BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
KT="${KAFKA_TOPICS_BIN:-/opt/kafka/bin/kafka-topics.sh}"
DIR="$(cd "$(dirname "$0")" && pwd)"
ensure() {  # name partitions compacted retention_ms
  local cfg=(--config min.insync.replicas=1 --config compression.type=producer)
  if [[ $3 == yes ]]; then
    cfg+=(--config cleanup.policy=compact --config min.cleanable.dirty.ratio=0.1 --config delete.retention.ms=86400000 --config segment.ms=3600000)
  else
    cfg+=(--config cleanup.policy=delete --config "retention.ms=$4")
  fi
  "$KT" --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic "$1" \
        --partitions "$2" --replication-factor 1 "${cfg[@]}" >/dev/null
  echo "OK $1"
}
while IFS=, read -r name pdev _pprod compacted _tomb _owner; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  ensure "$name" "$pdev" "$compacted" 604800000          # 7 d locally
  ensure "${name}.dlq" 1 no 2592000000                   # DLQ per topic (kernel K4.3), 30 d
done < "$DIR/topics.csv"
ensure _connect-configs 1 yes -
ensure _connect-offsets 25 yes -
ensure _connect-status 5 yes -
ensure __debezium-heartbeat.dbz.bitspay 1 no 86400000

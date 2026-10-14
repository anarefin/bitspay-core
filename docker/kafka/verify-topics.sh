#!/usr/bin/env bash
# Compares live partition counts with topics.csv; exits non-zero on drift. Run inside the kafka container.
set -euo pipefail
BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
KT="${KAFKA_TOPICS_BIN:-/opt/kafka/bin/kafka-topics.sh}"
DIR="$(cd "$(dirname "$0")" && pwd)"
rc=0
while IFS=, read -r name pdev _rest; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  live="$("$KT" --bootstrap-server "$BOOTSTRAP" --describe --topic "$name" 2>/dev/null | sed -n 's/.*PartitionCount: *\([0-9]*\).*/\1/p' | head -1)"
  if [[ "$live" != "$pdev" ]]; then echo "DRIFT $name: live=${live:-missing} expected=$pdev"; rc=1; fi
done < "$DIR/topics.csv"
[[ $rc -eq 0 ]] && echo "topics OK"
exit $rc

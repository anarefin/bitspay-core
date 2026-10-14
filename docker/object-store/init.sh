#!/bin/sh
# Creates the buckets services expect (SPEC §3.3 of wallet, disbursement, support, compliance, finance-ops).
set -eu
# Runs in the aws-cli image (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from compose). Idempotent.
S3="aws --endpoint-url http://object-store:9000 s3api"
i=0
until $S3 list-buckets >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && { echo "object store not reachable" >&2; exit 1; }; sleep 2
done
for b in bitspay-docs bitspay-reports bitspay-archive bitspay-restore; do
  $S3 head-bucket --bucket "$b" >/dev/null 2>&1 || $S3 create-bucket --bucket "$b" >/dev/null
  echo "OK $b"
done

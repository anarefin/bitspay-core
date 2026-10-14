#!/bin/sh
# Single replica, --development and a small cache grid: laptops only.
set -eu
F=/data/0_0.tigerbeetle
[ -f "$F" ] || /tigerbeetle format --cluster=0 --replica=0 --replica-count=1 --development "$F"
exec /tigerbeetle start --addresses=0.0.0.0:3001 --development --cache-grid=256MiB "$F"

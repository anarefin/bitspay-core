#!/usr/bin/env bash
# Runs a Gradle task in several standalone service builds, JOBS at a time.
#   scripts/gradle-each.sh ALL bootJar
#   scripts/gradle-each.sh "ledger-service wallet-service" check
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JOBS="${JOBS:-3}"
[ $# -ge 2 ] || { echo "usage: $0 <ALL|\"svc ...\"> <gradle args...>" >&2; exit 1; }
list="$1"; shift
[ "$list" = ALL ] && list="$(cd "$ROOT/services" && ls -d *-service)"
for s in $list; do
  [ -x "$ROOT/services/$s/gradlew" ] || { echo "services/$s/gradlew missing (run: cd services/$s && gradle wrapper)" >&2; exit 1; }
done
# The service is appended as the last argument (no -I: BSD xargs caps -I commands at 255 bytes).
printf '%s\n' $list | xargs -P "$JOBS" -n 1 bash -c '
  root="$1"; shift; s="${@: -1}"; set -- "${@:1:$#-1}"
  cd "$root/services/$s" && if ./gradlew --console=plain -q "$@" > "build-each.log" 2>&1; then echo "OK   $s"; rm -f build-each.log;
  else echo "FAIL $s (see services/$s/build-each.log)"; exit 1; fi' _ "$ROOT" "$@"

#!/usr/bin/env bash
# Service-scope lock for AI agents. While locked, agent hooks and the git pre-commit hook refuse changes to any
# other services/<svc>/ folder. Rules live in scripts/scope_check.py; how-to in docs/SERVICE-IMPLEMENTATION-STEPS.md.
#   scripts/scope.sh lock <service>  ·  unlock  ·  status  ·  check <path>...  ·  hooks
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$ROOT/.agent-scope"

install_hooks() {
  if [ "$(git -C "$ROOT" config core.hooksPath || true)" != "scripts/git-hooks" ]; then
    if git -C "$ROOT" config core.hooksPath scripts/git-hooks; then
      echo "Installed git hooks (core.hooksPath=scripts/git-hooks)"
    else
      echo "WARNING: could not install git hooks — run: git config core.hooksPath scripts/git-hooks" >&2
    fi
  fi
}

case "${1:-status}" in
  lock)
    svc="${2:-}"
    if [ -z "$svc" ] || [ ! -d "$ROOT/services/$svc" ]; then
      echo "usage: make lock svc=<service>   (one of: $(ls "$ROOT/services" | tr '\n' ' '))" >&2; exit 1
    fi
    echo "$svc" > "$LOCK"
    install_hooks
    echo "Scope locked to $svc — agents may change services/$svc/ and root files, no other service."
    ;;
  unlock)
    rm -f "$LOCK"; echo "Scope unlocked — agents may change any service." ;;
  status)
    if [ -s "$LOCK" ]; then echo "Scope locked to $(cat "$LOCK")"; else echo "Scope unlocked"; fi ;;
  check)
    shift; exec python3 "$ROOT/scripts/scope_check.py" paths "$@" ;;
  hooks)
    install_hooks ;;
  *)
    sed -n '2,4p' "$0" >&2; exit 64 ;;
esac

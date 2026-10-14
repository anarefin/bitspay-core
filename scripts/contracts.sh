#!/usr/bin/env bash
# Runs docs/global/tools/contracts.py against the monorepo. The tool expects the v6 pack layout
# (00-global/ + services/<NN>-<svc>/), so this builds a symlink view of it in .contracts-view/.
#   scripts/contracts.sh check [service]   ·   scripts/contracts.sh snapshot all   ·   scripts/contracts.sh index
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$ROOT/.contracts-view"
PACKS="01-ledger-service 02-transaction-service 03-wallet-service 05-limits-risk-service 06-pricing-service 07-treasury-service 08-disbursement-service 09-support-service 11-compliance-service 12-finance-ops-service 15-admin-service 16-general-ledger-service"
rm -rf "$V"; mkdir -p "$V/services"
ln -s ../docs/global "$V/00-global"
for p in $PACKS; do ln -s "../../services/${p#*-}/docs" "$V/services/$p"; done
exec python3 "$V/00-global/tools/contracts.py" "$@"

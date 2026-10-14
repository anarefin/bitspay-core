#!/usr/bin/env bash
# One database `bitspay`, one schema + login role per service (kernel K8.2). Runs once on an empty volume.
set -euo pipefail
SCHEMAS="svc_ledger svc_transaction svc_wallet svc_limits_risk svc_pricing svc_treasury svc_disbursement svc_support svc_compliance svc_finance_ops svc_admin svc_general_ledger"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bitspay <<SQL
REVOKE ALL ON DATABASE bitspay FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SQL
for r in $SCHEMAS; do
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bitspay <<SQL
CREATE ROLE ${r} LOGIN PASSWORD '${PG_SERVICE_PASSWORD}';
GRANT CONNECT ON DATABASE bitspay TO ${r};
CREATE SCHEMA ${r} AUTHORIZATION ${r};
ALTER ROLE ${r} SET search_path = ${r};
SQL
done

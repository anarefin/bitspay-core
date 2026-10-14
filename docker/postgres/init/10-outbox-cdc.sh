#!/usr/bin/env bash
# Outbox per service (kernel K8.2 DDL, owned by the service role) + Debezium role and publication.
set -euo pipefail
SCHEMAS="svc_ledger svc_transaction svc_wallet svc_limits_risk svc_pricing svc_treasury svc_disbursement svc_support svc_compliance svc_finance_ops svc_admin svc_general_ledger"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bitspay \
  -c "CREATE ROLE debezium LOGIN REPLICATION PASSWORD '${PG_DEBEZIUM_PASSWORD}'" \
  -c "GRANT CONNECT ON DATABASE bitspay TO debezium"
TABLES=""
for r in $SCHEMAS; do
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bitspay <<SQL
SET ROLE ${r};
CREATE TABLE IF NOT EXISTS ${r}.outbox (
  id uuid PRIMARY KEY, aggregate_type text NOT NULL, aggregate_id text NOT NULL,
  event_type text NOT NULL, payload jsonb NULL,
  created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON ${r}.outbox (created_at) WHERE published_at IS NULL;
GRANT USAGE ON SCHEMA ${r} TO debezium;
GRANT SELECT ON ${r}.outbox TO debezium;
RESET ROLE;
SQL
  TABLES="${TABLES:+$TABLES, }${r}.outbox"
done
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d bitspay -c "CREATE PUBLICATION dbz_outbox FOR TABLE ${TABLES}"

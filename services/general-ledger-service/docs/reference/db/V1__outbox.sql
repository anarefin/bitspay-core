-- Standard outbox (ENGINEERING-STANDARDS §4, catalogue v1.4 §12.2 — payload NULLABLE, C-004/D-31).
-- The local stack pre-creates svc_general_ledger.outbox (LOCAL-STACK §4.3 + GL addendum 06 §2); IF NOT EXISTS keeps
-- Testcontainers and the stack both working. Lands in schema svc_general_ledger via search_path.
-- general-ledger-service never writes tombstones (gl.events is not compacted), so payload is always set in practice.
CREATE TABLE IF NOT EXISTS outbox (
  id             uuid PRIMARY KEY,           -- = envelope eventId (UUIDv7)
  aggregate_type text        NOT NULL,       -- = Kafka topic name: 'gl.events', 'approval.events', 'audit.events', 'notification.requests'
  aggregate_id   text        NOT NULL,       -- = Kafka key = envelope aggregateId
  event_type     text        NOT NULL,
  payload        jsonb,                      -- full envelope (catalogue §7.1)
  created_at     timestamptz NOT NULL DEFAULT now(),
  published_at   timestamptz                 -- polling relay only
);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;

-- V2__gl_schema.sql — general-ledger-service (SVC-16 §4). Schema svc_general_ledger (search_path), PostgreSQL 18.
-- Money: bigint poisha. Signed balances are stored as NET DEBIT (debit positive, credit negative) — SVC-16 BR-GL-02.
-- Nothing here is ever UPDATEd after POSTED except status transitions named in §8; corrections are new journals.

-- ===================================================================== 1. Chart of accounts (§8.1)
CREATE TABLE gl_account (
  code                   text PRIMARY KEY CHECK (code ~ '^[0-9]{4}(-[0-9]{2})?$'),
  name_en                text NOT NULL CHECK (length(name_en) BETWEEN 1 AND 120),
  name_bn                text CHECK (name_bn IS NULL OR length(name_bn) BETWEEN 1 AND 120),
  account_class          text NOT NULL CHECK (account_class IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')),
  normal_side            text NOT NULL CHECK (normal_side IN ('DEBIT','CREDIT')),
  contra                 boolean NOT NULL DEFAULT false,
  parent_code            text REFERENCES gl_account(code),
  level                  smallint NOT NULL CHECK (level BETWEEN 1 AND 6),
  postable               boolean NOT NULL,
  ledger_controlled      boolean NOT NULL DEFAULT false,   -- balance must equal a TigerBeetle aggregate (GL-3, recon GL_TIEOUT)
  manual_posting_allowed boolean NOT NULL DEFAULT true,
  must_be_zero           boolean NOT NULL DEFAULT false,   -- 1950, 1999 (GL-5)
  template_code          text,                             -- '1101-{nn}': instances are created from this account
  description            text,
  status                 text NOT NULL CHECK (status IN ('PENDING_APPROVAL','ACTIVE','INACTIVE')),
  provisional            boolean NOT NULL DEFAULT false,
  effective_from         date NOT NULL,
  created_by             text NOT NULL,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  version                bigint NOT NULL DEFAULT 0,
  CHECK (NOT (ledger_controlled AND manual_posting_allowed)),
  CHECK ((normal_side = 'DEBIT') = ((account_class IN ('ASSET','EXPENSE')) <> contra))
);
CREATE INDEX gl_account_parent ON gl_account (parent_code);

-- ===================================================================== 2. Posting rules (§8.3)
CREATE TABLE gl_rule_set (
  version        int PRIMARY KEY,
  status         text NOT NULL CHECK (status IN ('DRAFT','PENDING_APPROVAL','APPROVED','SUPERSEDED','REJECTED','CANCELLED')),
                                                 -- SUPERSEDED: replaced by a newer APPROVED set with the same effective_from
  effective_from date NOT NULL,                  -- business date from which the set applies (never in a CLOSED period)
  description    text NOT NULL,
  checksum       text NOT NULL,                  -- sha256 of the canonical rules JSON
  provisional    boolean NOT NULL DEFAULT false,
  created_by     text NOT NULL,
  approved_by    text[] NOT NULL DEFAULT '{}',
  approval_id    uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  activated_at   timestamptz
);
CREATE UNIQUE INDEX gl_rule_set_effective ON gl_rule_set (effective_from) WHERE status = 'APPROVED';

CREATE TABLE gl_posting_rule (
  rule_set_version          int  NOT NULL REFERENCES gl_rule_set(version),
  rule_id                   text NOT NULL CHECK (rule_id ~ '^[A-Z0-9-]{1,32}$'),
  priority                  int  NOT NULL CHECK (priority BETWEEN 1 AND 999),
  tb_account_type           int  NOT NULL,
  side                      text CHECK (side IN ('DEBIT','CREDIT')),
  transfer_code             int,
  command_type              int CHECK (command_type BETWEEN 1 AND 19),
  leg_index                 int CHECK (leg_index BETWEEN 0 AND 5),
  reason_code               text CHECK (reason_code IS NULL OR length(reason_code) BETWEEN 1 AND 40),
  counterparty_account_type int,
  gl_account_code           text NOT NULL,       -- postable code or template '1101-{nn}'
  note                      text,
  PRIMARY KEY (rule_set_version, rule_id)
);

-- ===================================================================== 3. Ledger account registry (§8.2)
CREATE TABLE gl_ledger_account (
  account_id      uuid PRIMARY KEY,
  tb_account_type int  NOT NULL,
  bucket          text NOT NULL,                 -- 'WALLET:C' · 'SYS:FEE_INCOME' · 'TRUST:01'
  wallet_type     char(1) CHECK (wallet_type IN ('C','A','D','M','I','B')),
  trust_index     smallint CHECK (trust_index BETWEEN 1 AND 99),
  source          text NOT NULL CHECK (source IN ('FIXED','WALLET_EVENT','LEDGER_LOOKUP')),
  source_version  bigint,                        -- wallet.events version
  first_seen_at   timestamptz NOT NULL DEFAULT now()
);

-- ===================================================================== 4. Ingestion (§8.4)
-- Kafka offsets live HERE, written in the same DB transaction as the summary upserts (exactly-once; ADR-GL-03).
CREATE TABLE gl_ingest_offset (
  topic        text NOT NULL,
  partition    int  NOT NULL,
  next_offset  bigint NOT NULL,                  -- updated only with compare-and-set on the batch's start offset (BR-GL-31)
  max_tb_ts    bigint,                           -- greatest TB timestamp (ns) applied from this partition; legs with
                                                 -- timestamp <= max_tb_ts are producer re-publications and are skipped (BR-GL-30a)
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (topic, partition)
);

-- Stage 1: sub-ledger summary — one row per rule-relevant attribute combination (pre-mapping, re-mappable).
CREATE TABLE gl_subledger_summary (
  posting_date              date   NOT NULL,     -- GL day the amount belongs to (= value_date unless the period was closed)
  value_date                date   NOT NULL,     -- businessDate of the TB timestamp (CUTOFF.EOD)
  bucket                    text   NOT NULL,
  tb_account_type           int    NOT NULL,
  side                      text   NOT NULL CHECK (side IN ('DEBIT','CREDIT')),
  transfer_code             int    NOT NULL,
  command_type              int    NOT NULL,
  leg_index                 int    NOT NULL,
  reason_code               text   NOT NULL DEFAULT '',
  counterparty_account_type int    NOT NULL,
  amount_poisha             bigint NOT NULL CHECK (amount_poisha >= 0),
  leg_count                 bigint NOT NULL CHECK (leg_count >= 0),
  first_tb_ts               bigint NOT NULL,
  last_tb_ts                bigint NOT NULL,
  updated_at                timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (posting_date, value_date, bucket, side, transfer_code, command_type, leg_index, reason_code, counterparty_account_type)
);

-- Deferred legs (BR-GL-34): a reason-keyed rule could match and the reason is unknown, or the wallet is not yet in the
-- registry. Rows are kept after resolution (dedupe by transfer_id; re-keying when a late fact arrives after a timeout).
CREATE TABLE gl_command_reason (
  command_id  uuid PRIMARY KEY,
  reason_code text NOT NULL CHECK (length(reason_code) BETWEEN 1 AND 40),   -- as catalogue §2.5.11 (1..40 chars)
  source      text NOT NULL CHECK (source IN ('LEDGER_EVENT','TREASURY_EVENT')),
  received_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE gl_deferred_transfer (
  transfer_id    uuid PRIMARY KEY,
  command_id     uuid NOT NULL,
  value_date     date NOT NULL,
  data           jsonb NOT NULL,                 -- the ledger.changes data object
  cause          text NOT NULL CHECK (cause IN ('REASON','UNKNOWN_ACCOUNT')),
  deferred_until timestamptz NOT NULL,
  resolved_at    timestamptz,
  resolution     text CHECK (resolution IN ('RESOLVED','TIMEOUT_TO_1999','REKEYED')),
  summary_key    jsonb,                          -- the summary key the leg was booked under (needed to re-key after a timeout)
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX gl_deferred_open ON gl_deferred_transfer (value_date) WHERE resolved_at IS NULL;
CREATE INDEX gl_deferred_by_command ON gl_deferred_transfer (command_id);

-- TB counters of trust (and, with CCR-GL-02, system) accounts at the last event of each day (GL-3).
CREATE TABLE gl_tb_snapshot (
  value_date      date   NOT NULL,
  account_id      uuid   NOT NULL,
  last_tb_ts      bigint NOT NULL,
  debits_posted   bigint NOT NULL,
  credits_posted  bigint NOT NULL,
  PRIMARY KEY (value_date, account_id)
);

-- ===================================================================== 5. Calendar: days, periods, fiscal years (§8.6, §8.9)
CREATE TABLE gl_fiscal_year (
  fiscal_year        text PRIMARY KEY CHECK (fiscal_year ~ '^FY[0-9]{4}-[0-9]{2}$'),   -- FY2026-27
  from_date          date NOT NULL,
  to_date            date NOT NULL,
  status             text NOT NULL CHECK (status IN ('OPEN','CLOSING','CLOSED')),
  closing_journal_id uuid,
  closed_at          timestamptz,
  version            bigint NOT NULL DEFAULT 0
);
CREATE TABLE gl_period (
  period_id    text PRIMARY KEY CHECK (period_id ~ '^[0-9]{4}-[0-9]{2}$'),             -- calendar month 2026-10
  fiscal_year  text NOT NULL REFERENCES gl_fiscal_year(fiscal_year),
  from_date    date NOT NULL,
  to_date      date NOT NULL,
  status       text NOT NULL CHECK (status IN ('OPEN','CLOSING','CLOSED')),
  closed_at    timestamptz,
  reopen_count int NOT NULL DEFAULT 0,
  version      bigint NOT NULL DEFAULT 0
);
CREATE TABLE gl_day (
  business_date     date PRIMARY KEY,
  period_id         text NOT NULL REFERENCES gl_period(period_id),
  status            text NOT NULL CHECK (status IN ('OPEN','AWAITING_WATERMARK','CLOSING','CLOSED','CLOSED_WITH_EXCEPTIONS','FAILED','RESTATING')),
  revision          int  NOT NULL DEFAULT 0,
  dirty             boolean NOT NULL DEFAULT false,
  forced            boolean NOT NULL DEFAULT false,
  certification     text NOT NULL DEFAULT 'PENDING' CHECK (certification IN ('PENDING','CERTIFIED','FAILED','NOT_REQUIRED')),
  certified_run_id  uuid,
  rule_set_version  int,
  ledger_journal_id uuid,
  checks            jsonb,
  closed_at         timestamptz,
  version           bigint NOT NULL DEFAULT 0
);

-- ===================================================================== 6. Journals (§8.5, §8.7)
CREATE TABLE gl_journal (
  journal_id          uuid PRIMARY KEY,
  journal_ref         text NOT NULL UNIQUE,      -- GLJ-20261009-L-R1 · GLJ-20261010-M-000123 · GLJ-20270701-Y-000001
  source              text NOT NULL CHECK (source IN ('LEDGER_DAY','MANUAL','ACCRUAL','ACCRUAL_REVERSAL',
                                                       'REVERSAL','AUTO_INTEREST','YEAR_END_CLOSE','OPENING_BALANCE')),
  business_date       date NOT NULL,             -- the GL day the journal posts into
  revision            int,                       -- LEDGER_DAY only
  status              text NOT NULL CHECK (status IN ('PENDING_APPROVAL','POSTED','SUPERSEDED','REJECTED','CANCELLED')),
  narration           text NOT NULL CHECK (length(narration) BETWEEN 1 AND 500),
  document_reference  text CHECK (document_reference IS NULL OR length(document_reference) <= 64),
  reverses_journal_id uuid REFERENCES gl_journal(journal_id),
  auto_reverse_on     date,
  rule_set_version    int,
  total_debit_poisha  bigint NOT NULL,
  total_credit_poisha bigint NOT NULL,
  line_count          int NOT NULL,
  maker_id            text,
  checker_ids         text[] NOT NULL DEFAULT '{}',
  approval_id         uuid,
  idempotency_key     text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  posted_at           timestamptz,
  CHECK (total_debit_poisha = total_credit_poisha),
  CHECK (source <> 'LEDGER_DAY' OR revision IS NOT NULL)
);
CREATE UNIQUE INDEX gl_journal_ledger_day ON gl_journal (business_date, revision) WHERE source = 'LEDGER_DAY';
CREATE INDEX gl_journal_by_date ON gl_journal (business_date, status);

CREATE TABLE gl_journal_line (
  journal_id        uuid NOT NULL REFERENCES gl_journal(journal_id),
  line_no           int  NOT NULL,
  gl_account_code   text NOT NULL REFERENCES gl_account(code),
  side              text NOT NULL CHECK (side IN ('DEBIT','CREDIT')),
  amount_poisha     bigint NOT NULL CHECK (amount_poisha > 0),
  value_date        date,                        -- ledger lines: TB businessDate; ≠ business_date for late legs routed past a closed period
  product           text,                        -- P2P, CASH_IN, … (command type), null for manual lines
  transfer_code     int,
  source_bucket     text,                        -- WALLET:C · SYS:FEE_INCOME · TRUST (ledger lines only)
  trust_index       smallint,
  reason_code       text,
  rule_id           text,
  leg_count         bigint,
  narration         text CHECK (narration IS NULL OR length(narration) <= 200),
  PRIMARY KEY (journal_id, line_no)
);
CREATE INDEX gl_journal_line_account ON gl_journal_line (gl_account_code);

-- Daily balances per GL account and day revision (§8.6 step 5). Reports read only this table + the open-day overlay.
CREATE TABLE gl_daily_balance (
  business_date             date   NOT NULL,
  revision                  int    NOT NULL,
  gl_account_code           text   NOT NULL REFERENCES gl_account(code),
  opening_net_debit_poisha  bigint NOT NULL,
  debit_movement_poisha     bigint NOT NULL,
  credit_movement_poisha    bigint NOT NULL,
  closing_net_debit_poisha  bigint NOT NULL,
  PRIMARY KEY (business_date, revision, gl_account_code),
  CHECK (closing_net_debit_poisha = opening_net_debit_poisha + debit_movement_poisha - credit_movement_poisha)
);

-- Control totals per ledger bucket (cumulative, posted only) — served to reconciliation (catalogue GL addendum §11.5.2).
CREATE TABLE gl_control_total (
  business_date         date   NOT NULL,
  revision              int    NOT NULL,
  bucket                text   NOT NULL,         -- recon naming: WALLET:C · SYS:FEE_INCOME · TRUST
  trust_index           smallint NOT NULL DEFAULT 0,
  debits_posted_poisha  bigint NOT NULL,
  credits_posted_poisha bigint NOT NULL,
  day_debit_poisha      bigint NOT NULL,
  day_credit_poisha     bigint NOT NULL,
  leg_count             bigint NOT NULL,
  PRIMARY KEY (business_date, revision, bucket, trust_index)
);

-- ===================================================================== 8. Exceptions (§8.11)
CREATE TABLE gl_exception (
  id            uuid PRIMARY KEY,
  category      text NOT NULL CHECK (category IN ('UNMAPPED_POSTING','UNKNOWN_LEDGER_ACCOUNT','INVALID_LEDGER_EVENT','CLOSE_CHECK_FAILED',
                                                   'CONTROL_BREAK','MUST_BE_ZERO_BREAK',
                                                   'LATE_LEDGER_EVENT','PRIOR_PERIOD_LATE_EVENT','ENRICHMENT_TIMEOUT',
                                                   'CERTIFICATION_FAILED','DAY_CLOSE_BLOCKED','NORMAL_BALANCE_VIOLATION')),
  severity      text NOT NULL CHECK (severity IN ('CRITICAL','HIGH','INFO')),
  business_date date,
  detail        jsonb NOT NULL,
  status        text NOT NULL CHECK (status IN ('OPEN','RESOLVED')),
  resolved_by   text,
  resolution    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  resolved_at   timestamptz
);
CREATE INDEX gl_exception_open ON gl_exception (status, severity, business_date);

-- ===================================================================== 9. Standard tables (standards §4, catalogue §8.1)
CREATE TABLE processed_event (event_id uuid PRIMARY KEY, topic text NOT NULL, processed_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE idempotency_record (
  actor_id text NOT NULL, idem_key text NOT NULL, request_sha256 text NOT NULL, response_status int NOT NULL,
  response_body jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (actor_id, idem_key));
CREATE TABLE shedlock (name varchar(64) PRIMARY KEY, lock_until timestamptz NOT NULL, locked_at timestamptz NOT NULL, locked_by varchar(255) NOT NULL);
CREATE TABLE approval_request (
  id              uuid PRIMARY KEY,
  entity_type     text NOT NULL CHECK (entity_type IN ('GlAccount','PostingRuleSet','GlManualJournal','GlJournalReversal',
                                                       'GlOpeningBalance','GlDayForceClose','GlDayRestatement','GlPeriodClose',
                                                       'GlPeriodReopen','GlYearClose')),
  entity_id       text NOT NULL,
  action          text NOT NULL,
  payload         jsonb NOT NULL,
  maker_id        text NOT NULL,
  maker_user_id   text,
  status          text NOT NULL CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CANCELLED')),
  level           int  NOT NULL DEFAULT 1,
  required_levels int  NOT NULL DEFAULT 1 CHECK (required_levels BETWEEN 1 AND 3),
  checker_roles   text[] NOT NULL,
  amount_poisha   bigint,
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL,
  decided_by      text[] NOT NULL DEFAULT '{}',
  decided_at      timestamptz,
  version         bigint NOT NULL DEFAULT 0
);
CREATE INDEX approval_request_pending ON approval_request (status, entity_type) WHERE status = 'PENDING';
CREATE TABLE system_param (code text PRIMARY KEY, value text NOT NULL, source_version bigint);  -- refdata projection

-- ===================================================================== 10. Fixed ledger accounts (catalogue §2.1)
INSERT INTO gl_ledger_account (account_id, tb_account_type, bucket, source) VALUES
  ('00000000-0000-0000-0000-000000000200', 200, 'SYS:FEE_INCOME', 'FIXED'),
  ('00000000-0000-0000-0000-000000000210', 210, 'SYS:VAT_PAYABLE', 'FIXED'),
  ('00000000-0000-0000-0000-000000000220', 220, 'SYS:COMMISSION_PAYABLE', 'FIXED'),
  ('00000000-0000-0000-0000-000000000230', 230, 'SYS:AIT_PAYABLE', 'FIXED'),
  ('00000000-0000-0000-0000-000000000240', 240, 'SYS:CAMPAIGN_FUNDING', 'FIXED'),
  ('00000000-0000-0000-0000-000000000400', 400, 'SYS:SUSPENSE', 'FIXED'),
  ('00000000-0000-0000-0000-000000000410', 410, 'SYS:ADJUSTMENT_CLEARING', 'FIXED'),
  ('00000000-0000-0000-0000-000000000420', 420, 'SYS:HOLD_CONTROL', 'FIXED');
INSERT INTO gl_ledger_account (account_id, tb_account_type, bucket, trust_index, source)
SELECT ('00000000-0000-0000-0000-0000000300' || lpad(n::text, 2, '0'))::uuid, 300, 'TRUST:' || lpad(n::text, 2, '0'), n, 'FIXED'
FROM generate_series(1, 99) AS n;

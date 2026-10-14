<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# general-ledger-service — agent instructions

You are implementing **general-ledger-service** (SVC-16) of Bits Pay: the Operator's official books. It ingests `ledger.changes` exactly once, maps every TigerBeetle leg to the chart of accounts with versioned posting rules, closes business days (trial balance, control checks GL-1…GL-7), keeps manual/accrual journals, closes months and fiscal years, produces trial balance / balance sheet / P&L and a daily ERP journal file. Back-office only (Swagger, no UI). This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages, §7 the business rules BR-GL-xx).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins, group ids, fieldsUsed).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), `gl.events` schemas/examples, `codes.yaml`, data contracts (`gl-export-generic-csv.v1.md`, golden vectors).
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).
6. `reference/` — Flyway V1–V4, CoA v0 CSV, rule set v1 YAML, posting universe, golden-day input streams and ledger stubs (implementation material owned by this pack).

## Commands
- `./gradlew check` · `./gradlew test --tests 'RuleEngineGoldenTest'` · `./gradlew integrationTest --tests 'LedgerIngestorIT'` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=general-ledger-service`, `make hybrid svc=general-ledger-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check general-ledger-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/`, `docs/fixtures/` and `reference/test-inputs/` — never read or import another service's code. Never wait for another service.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.
- Use the test names in SPEC §10/§11. Branch `general-ledger-service/wp-<n>-<slug>`.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_general_ledger` only. One outbox `svc_general_ledger.outbox`.
- Money is `long` poisha. The GL only **adds** posted amounts: no double/float, no multiplication, division or rounding. Tk presentation only via `BigDecimal.valueOf(poisha, 2)`.
- Never move money, never call `POST /v1/ledger/commands/*`. Ledger reads only: `GET /v1/ledger/accounts/{id}/balance` (account type), `balances:batchGet`, `system-balance-sheet` (panels).
- Exactly once: `ledger.changes` offsets live in `gl_ingest_offset`, written in the SAME DB transaction as the `gl_subledger_summary` upserts, updated by compare-and-set on the batch start offset; seek on assignment; skip `timestamp ≤ max_tb_ts`. Never rely on Kafka commits. Other topics use `processed_event`.
- Every TB leg → exactly one DEBIT and one CREDIT line of the same amount. Unmapped → 1999 + CRITICAL exception. Unknown wallet → ledger lookup, else defer, after 1 h 1999 + CRITICAL, re-key later. Never drop or guess. Pending and void legs produce no lines.
- Posting rules are data: one `RuleEngine` (most specific match, then priority) shared by ingestion, restatement, `:simulate` and the open-day overlay. Never hard-code a GL account for a ledger leg (only 1999 and the retained-earnings config are allowed).
- Ledger-controlled accounts take LEDGER_DAY lines only; manual/accrual/reversal/opening/interest lines on them → 400 `LEDGER_CONTROLLED_ACCOUNT`.
- Posted journals are immutable; corrections are new journals; LEDGER_DAY revisions supersede. CLOSED periods never change; late legs land on the first open day with their value date.
- Day locks: ingestion takes `pg_advisory_xact_lock_shared(hashtext('gl-day-<d>'))` (sorted); close/restatement take the exclusive lock.
- Every state change writes `audit.events` (and `approval.events` for maker-checker) via the outbox in the same DB transaction. Checker ≠ maker (and ≠ maker's `X-Actor-User-Id`); level-2 ≠ level-1. Approval execution re-validates.
- Business date = `localDate(TB timestamp @ Asia/Dhaka − CUTOFF.EOD)`; value date and posting date are different fields.
- The GL holds no personal data; never log or publish any. Problem `reason` values only from `codes.yaml → problemReasons`.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`, the golden vectors, the posting universe, the seed CoA/rules (seed changes are regenerated with the GL reference model and re-copied).
- Merged Flyway migrations (add `V<n>` instead).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-GL-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
Traditional layered (kernel K9 "Layout"): `com.bracits.bitspay.generalledger` — `controller` / `dto` / `service` (business logic, jobs, `ingest`, `close`, `rules`: CoA rules, `RuleEngine`, journal arithmetic, calendar, checks) / `repository` (Spring Data JPA; native `@Query` for batch upserts) / `entity` / `mapper` / `exception` / `client` (`HttpLedgerClient`, Kafka AdminClient, `GenericCsvV1` export format) / `messaging` (outbox, Kafka listeners, inbox) / `config` (incl. ShedLock).

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; events consumed twice and `ledger.changes` batches replayed (no double count); ≥ 100-thread concurrency tests on ingest vs close; `rules_goldenVectors_all` and both golden days byte-exact against `docs/contracts/provided/data/gl-posting-golden-vectors.v1.json`; jqwik properties (bucket totals = TB counters, journals balance, restatement idempotent); kill-between-commits and rebalance ITs.

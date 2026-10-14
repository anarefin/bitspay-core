<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# finance-ops-service — agent instructions

You are implementing **finance-ops-service** (SVC-12) of Bits Pay: one Spring Boot service with two modules — `reconciliation` (lead, Dev-6: ledger ↔ business matching, projection, EOD close, trial balance, e-money recon, GL tie-out, file recon, exceptions, adjustments) and `reporting` (Dev-7: Kafka → ClickHouse, statements/history, partner data, report catalogue, schedules, analytics, regulatory datasets) — plus a private `common` kernel. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages: WP-1, then WP-A2…A11 and WP-B2…B11).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins, group ids, fieldsUsed).
3. `docs/contracts/provided/*` — `openapi.yaml` (108 operations), `events/recon.events/*`, `codes.yaml`: binding.
4. `docs/contracts/consumed/*` — snapshots of everything used from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local,api,ingest,jobs'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=finance-ops-service`, `make hybrid svc=finance-ops-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check finance-ops-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests." Stay inside the module of the WP (`reconciliation/**` or `reporting/**`); `common/**` changes need the service lead.
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` and `docs/MODULES.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_finance_ops` only; one outbox `svc_finance_ops.outbox` for both modules. Reporting tables are prefixed `reporting_`; reporting's inbox is `reporting_processed_event`. Only the reporting module touches ClickHouse `rpt`.
- Modules talk only through `<module>.service.<Module>Facade` interfaces (+ `<module>.dto` records), enforced by `ArchitectureTest`; reporting reads reconciliation results through `ReconciliationFacade` in-process, never over HTTP and never from its tables.
- Money is `long` poisha. Statement amounts parse via `BigDecimal` → exact poisha; Tk strings only via `BigDecimal.valueOf(p, 2)`. No `double`/`float` for money.
- Never change balances. The only ledger command is `post-adjustment`, only from the reconciliation module (`reconciliation.service.AdjustmentService` via `common.client.HttpLedgerClient`), only from an APPROVED `adjustment_proposal`, with `commandId = adjustmentId` persisted before the call; retry an unknown outcome with the same commandId and body; a REJECTED is final.
- Projection writes are guarded by the TB timestamp (latest wins); null `*BalanceAfter` only for system accounts (delta per `transferId`), null for a wallet/trust account → DLQ.
- Running balances come only from the ledger's balance-after (trust accounts debit-normal). Never sum a stream to get a balance. Exact ClickHouse reads use `FINAL`/`argMax` and prune by `business_date`/`account_id`.
- `businessDate = localDate(ts@Asia/Dhaka − CUTOFF.EOD)` from `refdata.events` (default 00:00); EOD readiness = cut-off + `CUTOFF.EOD_GRACE_MINUTES` + partition watermarks. EOD never pauses ingestion.
- Matching is deterministic; ambiguous candidates are never auto-matched.
- No chart of accounts, GL summary or GL export here — general-ledger-service owns them; reconciliation only ties out `GET /v1/gl/days/{businessDate}/control-totals` (`GL_TIEOUT`).
- Report templates: one `SELECT` on `rpt.*`, `{name:Type}` parameters only, run as `reporting_ro`; never concatenate user input into SQL.
- Maker ≠ checker (also on `X-Actor-User-Id`); closer ≠ resolver; approvals expire after 72 h; every state change → `audit.events` in the same DB transaction; every staff/partner/service view and every download is audited, holder self-views go to `rpt.access_log`.
- `recon.events` key is always `runId`; only severity ≥ HIGH exceptions are published; notification variables are int64 poisha, never pre-formatted; `priority`/`language` null.
- PII never in logs; mask per kernel K2 and the masking matrix (SPEC BR-RPT-27); NID never stored.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml` (exception categories, run types, templates, entity types, `RCA-` prefix).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-FINOPS-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
Traditional layered (kernel K9 "Layout"): `com.bracits.bitspay.financeops` — `common` (`config` actor/`@RequiresActor`, `exception` problem, `messaging` outbox/inbox, `service` approval/calendar, `client` object storage + `HttpLedgerClient`) · `reconciliation.{controller,dto,service,repository,entity,mapper,exception,client,messaging,config}` + facade `reconciliation.service.ReconciliationFacade` · `reporting.{controller,dto,service,repository,entity,mapper,exception,client,messaging,config}` (ClickHouse via plain JDBC in `reporting.client`/`reporting.repository`) with feature sub-packages `ingest`, `statement`, `history`, `partnerdata`, `catalogue`, `render`, `schedule`, `marts`, `regulatory`, `analytics`, `adhoc`, `feeds`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; every consumed event delivered twice → one effect; ≥ 100-thread tests on projection upserts and adjustment approval; jqwik properties for projection order, trial-balance zero-sum, e-money identity, matching determinism, amount parsing and statement totals; the SPEC §7 worked examples (EOD day 110 150 975, matching table, GL tie-out, Rahim statement 22 850, Nirob settlement 24 396) as exact tests; ClickHouse-down test proves reconciliation unaffected.

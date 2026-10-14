<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# limits-risk-service — agent instructions

You are implementing **limits-risk-service** (SVC-05) of Bits Pay: the limits and fraud decision service on the payment hot path. `POST /v1/risk/evaluate` must answer in ≤ 50 ms p95 (limits part ≤ 10 ms). This folder is the whole world for this service.

Release scope (SRS v1.2, CR-LIMITSRISK-1): **MVP** evaluates P2P, CASH_IN, CASH_OUT, MERCHANT_PAYMENT, MERCHANT_REFUND, FLOAT_TRANSFER, `BILL_PAY` and `RECHARGE` (to party = biller wallet `B`, user category `BILLER`, no biller limits). `evaluate:batch` callers are R1+; self-limits and simulation R2. SPEC §10 tags each WP `[MVP]` or `[R1+]`.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), event schemas (`risk.alerts`, `blacklist.events`) and `codes.yaml`.
4. `docs/contracts/consumed/*` — snapshots of `txn.events`, `wallet.events`, `customer.events`, `partner.events`, `disbursement.events`, `approval.events`, `audit.events` (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, hashing K2, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local,api,worker'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=limits-risk-service`, `make hybrid svc=limits-risk-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check limits-risk-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_limits_risk` only. One outbox `svc_limits_risk.outbox`.
- Money and limits are `long` poisha; never `double`/`float` (ArchUnit on `service.limits`). Lua compares integers < 2^53 only.
- Never return ALLOW / ALLOW_AND_ALERT without a successful reservation. Redis critical unavailable → `503 DEPENDENCY_UNAVAILABLE`.
- Limit check + increment happens ONLY in `limit_reserve.lua`; release ONLY via `limit_release.lua` (idempotent, never below zero, marks `rel=1`); commit / re-apply ONLY via `limit_reapply.lua`. Do not "fix" counters elsewhere.
- Expiry only via the sweeper with the `txn.events` watermark guard (BR-05-19); a COMPLETED for an expired/released reservation re-applies its counters (BR-05-21). Batch reservations never auto-expire.
- Decision precedence: SERVICE_DISABLED > BLOCK > LIMIT_EXCEEDED > HOLD > STEP_UP > ALLOW_AND_ALERT > ALLOW. HTTP 200 for every decision; `usage` never null; `violatedLimit` is an object.
- Fraud rules are data (JSON DSL, SPEC §7.6). Never hard-code a rule in Java. Missing attribute = UNKNOWN.
- No synchronous calls to other services; no TigerBeetle; no refdata.
- Hash identifiers per kernel K2 (`BITSPAY_PLATFORM_HMAC_KEY`); NID / BANK_ACCOUNT only by `valueHash`; mask for display.
- Every config / list / rule / emergency change: maker-checker (checker ≠ maker) + `audit.events` + `approval.events` in the same DB transaction.
- Asia/Dhaka for calendar periods; UTC everywhere else.
- PII never in logs; mask per kernel K2.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml` (decision enum, limit-code grammar, reasons, metrics).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-LIMITSRISK-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.limitsrisk` — layered (global K9): `controller` / `dto` / `service` (evaluate, reservations, config, rules, lists, approvals, jobs; sub-packages `limits`, `fraud`, `lists` hold the rules and calculations) / `repository` (Spring Data JPA: `ConfigRepository`, `HistoryRepository`, …) / `entity` / `mapper` / `exception` / `client` (Redis: `RedisCounterStore`, `RedisAggregateStore`, `RedisProfileStore`; Lua in `src/main/resources/redis/`) / `messaging` (Kafka consumers, `OutboxWriter`, inbox) / `config` (incl. the `Clock` bean). No ports or adapters; `ArchitectureTest` enforces the layer rules.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*` (incl. `x-additional-examples`); consumer tests from `docs/contracts/consumed/*` and fixtures; every consumed event delivered twice; ≥ 200-thread concurrency tests in both `SINGLE_SLOT` and `PER_PARTY` modes with zero overshoot and zero clamped counters; one firing / non-firing test per seeded rule; DSL golden file ≥ 40 cases.

<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# treasury-service — agent instructions

You are implementing **treasury-service** of Bits Pay: trust accounts and trust-balance confirmations, e-money issuance / redemption with the EMY-009 hard control, trust rebalance (R2), manual journals, trust interest, float requests, liquidity monitoring and the e-money regulatory datasets. Back office only: APIs + Swagger, no UI. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages, §7 the business rules).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), event (`events/treasury.events/*`) and code (`codes.yaml`) contracts this service owns.
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from ledger-, transaction-, wallet- and admin-service (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=treasury-service`, `make hybrid svc=treasury-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check treasury-service`
- Swagger: `http://localhost:8000/treasury/swagger-ui.html` (ports 8107 / 9107)

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code (this includes ledger-service, even though the same developer owns it).
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_treasury` only. One outbox `svc_treasury.outbox`.
- Money is `long` poisha; statement decimals are parsed with `BigDecimal` scale 2 and converted exactly. No `double`/`float`.
- Never move money yourself: only ledger commands `post-emoney-issue`, `post-emoney-redeem`, `post-adjustment`, `post-trust-rebalance` (always `X-Actor-Type: SERVICE`, `X-Actor-Id: treasury-service`) or transaction-service `POST /v1/payments/float-transfer`. Ledger `commandId` = the entity id; retries reuse it; a `REJECTED` result is final.
- EMY-009: execute an issuance only inside `SELECT … FOR UPDATE` on the `trust_account` row, after reading the ledger mirror: `mirror + amount ≤ latest confirmed (age ≤ 26 h) + tolerance`, else `CONTROL_FAILED`. Rebalance: lock both rows in `trust_index` order, control on `to`.
- Unknown outcome → `POSTING_UNKNOWN` and resolve with `GET /v1/ledger/commands/{commandId}` (REJECTED → REJECTED_BY_LEDGER; found → POSTED; else re-post same body). Float transfers: 503/timeout → retry with the same `Idempotency-Key`; any 4xx → FAILED; > 24 h → look up `GET /v1/transactions?walletId=&clientReference=` first; never send a key 72 h after its first use.
- Float transfers forward the captured actor context of the owner of `fromWalletId` (approving parent / requester for an unapproved RETURN) or the STAFF approver — never treasury's own SERVICE identity.
- Maker-checker (kernel K5): checker ≠ maker, one level per checker, roles per SPEC §7.7; the last approval executes after the decision is committed. Every state change writes `audit.events` (and `approval.events` / `notification.requests` / `treasury.events` where relevant) through the outbox in the same DB transaction.
- `ledger.changes` is idempotent by TB timestamp per wallet (apply only if newer); do not insert `processed_event` for it. A null `*BalanceAfter` for a partner wallet goes to the DLQ.
- `businessDate = localDate(ts @ Asia/Dhaka − CUTOFF.EOD)` everywhere; `CUTOFF.EOD` comes from `refdata.events` (default 00:00). `CUTOFF.SETTLEMENT_BANK` is not read.
- Notification variables exactly as in `codes.yaml → notificationTemplates`: MONEY as int64 poisha, never pre-formatted; staff groups via `recipient.role`, one request per role; `priority: null`.
- Bank account numbers: `FieldCipher` + K2 hash + mask; never log, return unmasked or publish them. PII never in logs; mask per kernel K2.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-SVC07-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.treasury` — layered (global K9): `controller` (per tag) / `dto` / `service` (business logic, `ApprovalEngine`, jobs, `HardControl`, approval policy, threshold state machine, txnRef + business-date calculators, statement parsers, `FieldCipher`) / `repository` (Spring Data JPA; `@Query` / native for locking) / `entity` / `mapper` / `exception` / `client` (`HttpLedgerClient`, `HttpTransactionClient`, `HttpWalletClient`, `HttpAdminClient` with Resilience4j; `LocalFsObjectStore`) / `messaging` (outbox writer, Kafka consumers `ledger-changes` / `partner-projection` / `refdata`, inbox) / `config`. No ports or adapters; `ArchitectureTest` enforces the layer rules.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*` (56 operations, 9 event types); consumer tests from `docs/contracts/consumed/*`; events consumed twice; ≥ 100-thread concurrency tests on the hard control and float approval; jqwik property test that Σ posted issuances never exceeds the confirmed balance; statement parser golden files; the test names in SPEC §11.

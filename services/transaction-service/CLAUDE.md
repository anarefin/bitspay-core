<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# transaction-service — agent instructions

You are implementing **transaction-service** (SVC-02) of Bits Pay: the payment orchestrator (P2P, cash-in, cash-out, merchant payment and refund, float transfer, reversal executor, quote, queries). This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API/event/code contracts this service owns (`openapi.yaml`, `events/txn.events/*`, `codes.yaml`).
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from others (read-only): ledger, limits-risk, wallet, pricing (incl. `pricing-algorithm` and `pricing-golden-vectors`), admin.
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` (Fake ledger client, WireMock on 8099 for every other client) · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=transaction-service`, `make hybrid svc=transaction-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check transaction-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_transaction` only. One outbox `svc_transaction.outbox`.
- Money is `long` poisha. No `double`/`float`. `HALF_EVEN` rounding only inside the pricing evaluator, which must equal the consumed `pricing-algorithm` and pass every CATALOGUE golden vector — never "improve" it.
- Pipeline order is fixed: validate + product switch → idempotency claim → wallet status → risk evaluate → pricing → INSERT intent → ledger command → one DB transaction (conditional UPDATE + outbox) → reply. REVERSAL skips wallet status, risk and pricing.
- Never answer COMPLETED before the outcome and its outbox row are committed. Outcome updates are always `WHERE status = 'INITIATED'` (or the expected state); 0 rows = someone else won, return the stored state, write no event.
- Ledger timeout/5xx/503 = unknown: keep INITIATED, reply 503 with `transaction`. Never mark FAILED without `GET /v1/ledger/commands/{commandId}`.
- `commandId = txnId`; a re-sent command rebuilds the identical body from the stored row; a new attempt is a new intent (new key, new `txnId`).
- If wallet status, risk or pricing cannot be read → 503 `DEPENDENCY_UNAVAILABLE`. Never guess.
- Responses carry `transaction` iff the intent was persisted; problem extension members exactly as `codes.yaml → problemExtensions`.
- `txn.events` key = `fromWalletId` of the transaction in `data` (the original's for REVERSED/REFUNDED); `createdAt` = risk evaluate `at`.
- No `AUDIT_RECORDED` for customer payment outcomes; audit reversals, refunds, refund requests/decisions, float overrides, beneficiaries, anomaly resolutions.
- PII never in logs; never log `note` or `merchantReference`; mask per kernel K2.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml` (txnRef format, failureCode list, problem extensions, metrics).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-TX-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.transaction` — `controller` (controllers incl. profile-guarded DevController) / `dto` / `service` (PaymentPipeline, TxnTypePolicy impls, IdempotencyService, WalletStatusService, PricingSnapshotService, QuoteService, OutcomeRecorder, RecoverySweeper, LatePostVerifier, RefundApprovalService, jobs; DirectionRules, WalletTypeRules, FloatPairRules, TxnRefGenerator, pricing evaluator) / `repository` (Spring Data JPA: TxnRepository, projections, approvals, inbox) / `entity` (TxnIntent, TxnStatus transitions, TxnType, pricing value objects) / `mapper` / `exception` (ProblemMapper) / `client` (HttpLedgerClient + FakeLedgerClient behind `LedgerClient`, HttpLimitsRiskClient, HttpWalletClient, HttpPricingClient, Redis Lua IdempotencyStore, WalletStatusCache) / `messaging` (Kafka listeners, outbox writer + relay) / `config`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; consumed events delivered twice; ≥ 100-thread concurrency tests on idempotency, refunds and reversals; golden vectors byte-identical to the snapshot; chaos tests with Fake ledger `FAIL_AFTER_POST`; test names listed in SPEC §11 must exist.

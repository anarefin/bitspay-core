<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# disbursement-service — agent instructions

You are implementing **disbursement-service** (SVC-08) of Bits Pay: bulk disbursement batches, local maker-checker, scheduled transfers and request money. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), event (`events/disbursement.events/`) and code (`codes.yaml`) contracts this service owns.
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from wallet, ledger, limits-risk, transaction and admin services (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=disbursement-service`, `make hybrid svc=disbursement-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check disbursement-service`
- Local profile points the wallet / ledger / risk / transaction `Http<Svc>Client`s at WireMock on 8099 (`bitspay.clients.<svc>.base-url`); ports 8108 / 9108.

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.
- WP-10 (vouchers) is **blocked** until CCR-DS-08 is approved. Do not start it.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_disbursement` only. One outbox `svc_disbursement.outbox`; every event / notification / approval / audit row is written in the same transaction as the state change.
- Money is `long` poisha. Parse Taka from CSV with `BigDecimal` from the string (scale ≤ 2, × 100 exact). No double/float anywhere. Template MONEY variables are raw int64 poisha, never pre-formatted; MSISDN variables are full `8801…`, never pre-masked.
- Row `commandId` = `UUIDv5(batchId, decimal(rowNo))` (attempt 1) / `UUIDv5(batchId, rowNo + ":" + n)`. Persist `reserved = true` + the attempt's `commandId` BEFORE `evaluate:batch`, and the row PROCESSING (with the stored max-balance constraint) BEFORE the ledger call.
- A PROCESSING row is only ever re-posted with the same `commandId` and body. Never mark it FAILED without a ledger answer. The attempt changes only after a ledger `REJECTED`, a release of the current id, or a limits-risk 409 naming it.
- Every reserved attempt that will not be paid (FAILED, SKIPPED, reset to VALID) gets a `reservation_release` job in the same transaction; the job runs until a final state.
- Every state change is a conditional UPDATE on the expected status. Work claiming = `FOR UPDATE SKIP LOCKED` + leases. Respect the global throttle; never bypass it.
- Scheduled / request payments call transaction-service P2P with the payer's own identity (schedules: CUSTOMER headers + `X-Channel: SYSTEM`; accept: forwarded payer headers) and a stable `Idempotency-Key` (`sched-{scheduleId}-{yyyy-MM-dd}`, `preq-{requestId}-{attempt}`). Retry with the SAME key only after 503 / timeout and only for 20 h; then resolve by GET. Any 4xx is final for the key.
- On `:accept`, relay transaction-service problems unchanged (keep `transaction` and its other members) and add `paymentRequest`.
- No local reminder loop: register reminders with `notification.requests` `reminder{}` and emit `NOTIFICATION_REMINDER_CANCELLED`.
- Product switches (`DISBURSEMENT`, `SCHEDULED_TRANSFER`, `REQUEST_MONEY`) refuse new work with 422 `SERVICE_DISABLED` and pause accepted work — never fail it.
- Maker ≠ checker (actor and `X-Actor-User-Id`); funding check before start and resume.
- PII never in logs; mask MSISDN `8801711****00`; never log names from files, notes or file content.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-DS-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.disbursement` (layered: controller → service → repository / client / messaging) — `controller` (Batch, Approval, ScheduledTransfer, PaymentRequest, InternalAdmin controllers) / `dto` / `service` (intake, validation, approval, funding, execution, finaliser, release job, schedules, occurrences, requests, resolver, product switch; Msisdn, AmountParser, CommandIds, Recurrence, references) / `repository` (Spring Data JPA repositories, DB rate limiter) / `entity` (Batch, BatchRow, Chunk, Schedule, PaymentRequest + state machines, enums) / `mapper` / `exception` (problem mapper) / `client` (HttpWalletClient, HttpLedgerClient, HttpLimitsRiskClient, HttpTransactionClient; `FileStore` interface with `local-fs` and `s3` implementations) / `messaging` (outbox writer, refdata consumer, inbox) / `config` (ActorContext filter, `@RequiresActor`, idempotency filter).

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; the refdata fixture consumed twice; ≥ 100-thread concurrency tests on chunk claiming, accept and occurrence execution; chaos test "crash after ledger post → re-run pays nobody twice"; `commandId_uuidv5_knownVectors` (SPEC §7.4); jqwik for the amount parser and batch counters; test names listed in SPEC §10/§11 must exist.

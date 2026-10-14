<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# support-service — agent instructions

You are implementing **support-service** (SVC-09) of Bits Pay: tickets, SLA / escalation, disputes, wrong-transfer holds, reversal requests with maker-checker, service actions, customer 360, transaction enquiry, dashboards and the BB complaint dataset. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), `support.events` schemas and `codes.yaml` this service owns.
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=support-service`, `make hybrid svc=support-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check support-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code. Each dependency is one concrete `client.Http<Svc>Client`; tests and profile `local` point it at WireMock.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_support` only. One outbox `svc_support.outbox` (also carries `notification.requests`, `approval.events`, `audit.events` rows).
- Money is `long` poisha; no float/double. This service never moves money itself: money effects ONLY via ledger `create-hold` / `release-hold` and transaction-service `POST /v1/internal/reversals` (as `SERVICE` / `support-service`).
- A reversal is executed only by `ReversalExecutor` and only for an APPROVED local `approval_request`; checker ≠ maker and ≠ earlier-level checker (422 `MAKER_CHECKER_VIOLATION`).
- Reversal key per attempt: `Idempotency-Key = rev-{reversalRequestId}-{attempt}`. Same key ONLY after 503 / timeout / 5xx / connection error (stay EXECUTING, never mark FAILED on an unknown outcome). Any definitive 4xx/422 closes the attempt; the next one uses `attempt + 1`. Map responses exactly as SPEC BR-S-34 (incl. `LEDGER_HOLD_NOT_FOUND` → retry without `releaseHoldCommandId`).
- Holds: `commandId = UUIDv5(SUPPORT_NS, "hold:{disputeId}:{seq}")`, same id on every retry of an unknown outcome; a REJECTED hold is final — a new hold uses `seq + 1`. Amount = `min(requested, principal, available)`. Set wallet flag 8 after ACTIVE, clear it when the wallet has no more support holds. Never expire / release a hold whose dispute has a reversal APPROVED / EXECUTING / PENDING_FUNDS / FAILED_RETRYABLE.
- Match `txn.events TRANSACTION_REVERSED` by `data.txnRef` (the original) — never by `originalTxnRef`.
- Wallet status changes and contact updates are forwarded with the staff member's own `X-Actor-*` headers; completion comes from `approval.events` (group `support-service.approvals`, only `service = wallet-service` and `entityType ∈ {WalletStatusChange, CustomerProfile}`), never from `wallet.events`.
- `TICKET_UPDATE` is sent by this service (ticket created, customer-visible status change, dispute resolved) — NEVER for internal tickets (`REVERSAL_RECOMMENDATION`, tipping-off). `REVERSAL_RECOMMENDED` is never auto-executed.
- Notification variables exactly as `codes.yaml` (`…Poisha` int64, ISO-8601 UTC ms timestamps, full MSISDN — never pre-formatted / pre-masked); `priority: null`.
- `support.events`: key = `ticketId`, payloads exactly as the schemas; every dispute/reversal event has non-empty `walletIds[]`.
- Customer 360: per-section timeout 800 ms, total 1.5 s, partial results with section status; audit every view and every attachment download.
- `txnRef` is opaque (1..32 `[A-Z0-9-]`, columns `varchar(32)`); IVR / chatbot adaptors are `SYSTEM` actors with body `source`, never `X-Channel: IVR`.
- PII never in logs; mask MSISDN `8801711****00`; NID never stored; attachments AES-GCM encrypted; audit `before`/`after` per kernel K6.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-SUP-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.support` (layered: controller → service → repository / client / messaging) — `controller` / `dto` / `service` (ticket, dispute, hold, reversal incl. `ReversalExecutor`, service actions, customer 360, ShedLock jobs; `SlaClock`, `BusinessCalendar`, `ReversalEligibility`, `MaskingPolicy`, `CommandIds`) / `repository` (Spring Data JPA) / `entity` (`Ticket`, `Dispute`, `Hold`, `ReversalRequest`, `ApprovalRequest`, enums) / `mapper` / `exception` (problem+json advice) / `client` (`HttpTransactionClient`, `HttpLedgerClient`, `HttpWalletClient`, `HttpLimitsRiskClient`, `HttpFinanceOpsClient`, `HttpAdminClient`, `AttachmentStore` (S3), `ExternalTicketingProvider` interface — `none` implementation now, CRM implementations by config in R2) / `messaging` (outbox writer, inbox consumers) / `config` (ActorContext filter, `@RequiresActor`, ShedLock).

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; events consumed twice; ≥ 100-thread concurrency tests on ticket numbering, reversal execution and approvals; one test per row of the BR-S-34 mapping table; key-per-attempt and same-`commandId` retry tests; log-scan test for PII; business-calendar tests with weekend days and bank holidays.

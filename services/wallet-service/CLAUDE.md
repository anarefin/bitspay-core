<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# wallet-service — agent instructions

You are implementing **wallet-service** of Bits Pay: one Spring Boot service with two business modules, `wallet` (customers, KYC, wallets, lifecycle, closure, wallet status cache — owner Dev-3) and `partner` (agents, merchants, distributors, institutions, onboarding, hierarchy, Bangla QR — owner Dev-4), plus the service-private shared kernel `common`. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (§1.5 modules, §7 rules, §10 work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins, group ids).
3. `docs/contracts/provided/*` — binding contracts this service owns: `openapi.yaml` (102 operations), `events/` (wallet.events, customer.events, partner.events), `codes.yaml`, `data/wallet-status-cache.v1.md`.
4. `docs/contracts/consumed/*` — snapshots of everything used from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local,api,cache-loader'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=wallet-service`, `make hybrid svc=wallet-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check wallet-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests." State the module in every branch / MR: `wallet-service/<module>/wp-<n>-<slug>`.
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` (one section per module) and `docs/MODULES.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_wallet` only; one outbox `svc_wallet.outbox` for both modules; partner tables are prefixed `partner_`; inbox `processed_event` (wallet) / `partner_processed_event` (partner).
- Modules talk only through `<module>.service.<Module>Facade` interfaces + `<module>.dto` records (in-process; `ArchitectureTest`). No HTTP clients, stubs or retry tables between the modules; never touch the other module's tables or classes.
- Money is `long` poisha; this service never moves money itself and never talks to TigerBeetle. Ledger calls: account create / close, balance, holds, batch balances, command 17 `post-closure-payout` and its lookup only. Never close, pay out or anonymise on an unknown dependency state.
- Closure payout `commandId = UUIDv5(closureId, "payout:" + attempt)`, persisted before the call; attempt + 1 only after a definitive REJECTED; timeouts retry the same commandId and body.
- Wallet `version` increments by exactly 1 on every wallet row update; it is the cache version. Every applied restriction add / lift bumps it and sets `statusReasonCode`, even if the status letter is unchanged; NOOP emits nothing.
- Every wallet change: DB update + history + outbox (`wallet.events`, `audit.events`) in ONE transaction; Redis write-through only AFTER commit with the Lua CAS (never plain HSET, never HDEL). Cache format = `data/wallet-status-cache.v1.md`; its vectors must pass.
- Status = base status + restrictions (`StatusResolver`); never write `status_code` directly. SERVICE/SYSTEM + AML_FREEZE / FRAUD_FREEZE (compliance) and the partner module's `PARTNER_*` reasons are the only immediate paths; freezes lift only by exact `(reasonCode, reference)`.
- Never publish `WALLET_UPSERTED` for a non-READY wallet. `partner.events` carries ONLY `PARTNER_UPSERTED` with all 20 contract fields every time.
- Never auto-approve KYC: correlated CLEAR screening (sourceEventId), blacklist done, no open exception, checker ≠ maker. `eddRequired` holds like a potential match.
- PII: NID / bank account numbers only encrypted (FieldCipher) + HMAC (kernel K2); blacklist checks always with `valueHash`; never log NID, full MSISDN, account numbers, document bytes or dynamic QR payloads.
- QR decode trusts the database, not the QR text; amounts via BigDecimal only.
- Consumers: inbox row + effect in one transaction; 5 retries then `<topic>.dlq`; unknown types counted with `bitspay_consumer_events_ignored_total`.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml` (incl. category codes, reason codes, templates).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-WALLET-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.WalletServiceApplication`; `com.bracits.bitspay.wallet` and `com.bracits.bitspay.partner` — each `controller` / `dto` / `service` (incl. the public `WalletFacade` / `PartnerFacade`) / `repository` / `entity` / `mapper` / `exception` / `client` / `messaging` / `config`; `com.bracits.bitspay.common` — shared config (ActorContext filter, `@RequiresActor`, ShedLock), exception (problem mapper), messaging (outbox / inbox, DLQ), idempotency, maker-checker engine, FieldCipher, HmacHasher, clients (DocumentStore, `HttpLedgerClient`, `HttpLimitsRiskClient`, `HttpAdminClient`). Flyway `db/migration/wallet` (first) and `db/migration/partner`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*` (every example, every event schema, PARTNER_UPSERTED exact keys, cache vectors, QR golden vectors); consumer tests from `docs/contracts/consumed/*`; every consumed event delivered twice; ≥ 100-thread concurrency tests on status changes, registrations, stage approvals, hierarchy changes and closure settlement; partner ↔ wallet atomicity tests (rollback together, Redis after outer commit); PII log-scan test.

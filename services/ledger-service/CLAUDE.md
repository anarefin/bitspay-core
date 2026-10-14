<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# ledger-service — agent instructions

You are implementing **ledger-service** (SVC-01) of Bits Pay: the ONLY service that talks to TigerBeetle (TB). This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages, §7 the business rules, §5 the provided contracts).
2. `docs/contracts/contract.yaml` — what this service provides (19 commands + reads, incl. MVP bill payment 18 and recharge 19 to BILLER_WALLET 150; `ledger.changes`, transfer-id data contract) and consumes (only the inbound topic `audit.events`).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`), event schema (`events/ledger.changes/`), codes (`codes.yaml`), data contracts (`data/`).
4. `docs/contracts/consumed/*` — snapshot of admin-service's `audit.events` schema (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` (Docker required: TB 0.17.9, Postgres 18, RabbitMQ, Kafka via Testcontainers) · `./gradlew integrationTest --tests 'TbBehaviourSpikeIT'`
- `./gradlew bootRun --args='--spring.profiles.active=local,api'` · `--spring.profiles.active=local,cdc-bridge` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=ledger-service`, `make hybrid svc=ledger-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check ledger-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; never read or import another service's code.
- Write the test first for every TB behaviour you rely on; record findings in `docs/TB-NOTES.md` and ADRs in `docs/adr/`.
- Use the test names from SPEC §11.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_ledger` only. One outbox `svc_ledger.outbox` (only `audit.events` goes through it).
- Money is `long` poisha; TB u128 values are `UInt128`/`BigInteger`, narrowed with overflow checks; never `double`/`float`.
- Transfer ids = `transferId(commandId, legIndex)` = first 16 bytes of SHA-256(uuidBytes(commandId) || uint8(legIndex)), canonical UUID text. Never random. UUID → TB: `UInt128.asBytes(lo, hi)` (little-endian!). Golden vectors in `docs/contracts/provided/data/` must pass.
- Leg indexes fixed by position (0 principal, 1 fee, 2 VAT, 3 commission, 4 AIT, 5–8 bounds; reversal 0 = hold void, 1+i = mirror). Skipped legs keep gaps. A multi-leg command is ONE linked chain; never split a chain across TB requests.
- Unknown TB outcome (timeout/exception) → `503 DEPENDENCY_UNAVAILABLE`. Never guess, never void or reverse on a timeout.
- `REJECTED` is final per `commandId`: pre-TB rejections are written synchronously to `command_rejection` + journal before responding and checked before every TB submission; TB-level ones come back as `id_already_failed`.
- Idempotency is keyed on `commandId` only; `Idempotency-Key` is optional and ignored (log + metric). Hash = canonical body without `metadata`.
- Caller policy: `X-Actor-Type: SERVICE` and `X-Actor-Id` per SPEC §5.1.2 / `x-actors`; anything else → 403. pricing-service may reverse only type-12 originals with both flags false.
- Max balance only via the balance-bounds recipe; `bounds.mode=two-phase` never in a shared environment.
- Every non-technical account carries the TB `history` flag (flags are immutable — bootstrap must create them right).
- Never publish technical codes 9001–9099; never accept or report accounts 900/910.
- Account close uses flags `pending | closing_debit` only (SUSPENSE must stay open).
- Only `client.TbGateway` (with its batchers in `client`) imports `com.tigerbeetle.*`; controllers call services only (`ArchitectureTest`, ArchUnit).
- No PII exists here; log ids only. Read actor context only via `ActorContext`.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml` (account types, transfer codes, command types, rejection codes, detail tokens, system account ids, hold reason codes).
- Flyway migrations already merged (add `V<n>`).
- If a WP seems to need a contract change: stop, write `docs/changes/CR-LED-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.ledger` — `controller` (Command/Account/Query/Internal controllers) / `dto` / `service` (CommandService handlers, CallerPolicy, AccountService, QueryService, SystemAccountBootstrap, jobs; LegTemplates, TransferIds, ResultResolver, AccountTypeGuards, BalanceFormulas, RequestHasher) / `repository` (Spring Data JPA: journal + JournalWriter, rejections, holds, claims, registry) / `entity` / `mapper` / `exception` (problem mapper) / `client` (TbGateway, TbBatcher, ReadBatcher, AccountTypeCache) / `messaging` (outbox writer, CdcBridge, CdcPoller, Kafka producer, projection) / `config` (ActorContext filter, `@RequiresActor`). Run roles: `api`, `cdc-bridge`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*` (every operation, every `x-actors` entry, the `ledger.changes` schema); consumer test for the `audit.events` schema from `docs/contracts/consumed/`; `TbBehaviourSpikeIT` against TB 0.17.9; ≥ 100-thread concurrency tests (same commandId, P2P storm zero-sum, concurrent reversals, max balance never overshoots); jqwik properties (Σ debits = Σ credits per chain, bearer debit = amount + fee + VAT); CDC redelivery applies the projection once.

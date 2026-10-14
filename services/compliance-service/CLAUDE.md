<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# compliance-service — agent instructions

You are implementing **compliance-service** (SVC-11) of Bits Pay: AML/CFT and fraud-investigation back office — screening lists (file upload), fuzzy Bangla/English name matching, transaction monitoring scenarios, shared fraud/AML cases, freezes and liens, CTR extraction, STR/CTR goAML XML export, AML/fraud MIS. This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API (`openapi.yaml`, 74 operations), `case.events` schemas and `codes.yaml`.
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=compliance-service`, `make hybrid svc=compliance-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check compliance-service`
- Local: port 8111 (management 9111); WireMock for ledger/wallet/limits-risk/admin on 8099 (`local` profile).

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_compliance` only. One outbox `svc_compliance.outbox`.
- Money is `long` poisha; goAML amounts are formatted with integer arithmetic. Similarity scores may be `double` (not money); MIS rates are integer basis points.
- The only money-adjacent effects: ledger `create-hold` / `release-hold` (attempt-derived commandIds: `hold:{freezeId}`, `hold:{freezeId}:{n}`, `release:{freezeId}` under `NS_COMPLIANCE`; a new attempt only after a definitive REJECTED), wallet `status-changes` / `flags`, partner `status-changes` (SUSPENDED only).
- A freeze is APPLIED/LIFTED only on wallet `200 APPLIED|NOOP` or ledger `OK|EXISTS` (release also `HOLD_NOT_FOUND`). `wallet.events` never confirms a freeze. A wallet `202` for AML_FREEZE/FRAUD_FREEZE is an integration error.
- A lift always sends `targetStatus ACTIVE` with the freeze's own `reasonCode` and the exact `reference` sent on apply; never `DORMANT`, never a stored status-before. Comment is exactly `FREEZE <reference>` / `LIFT <reference>`.
- Never publish `SCREENING_COMPLETED` CLEAR unless screened against ALL active list versions and the blacklist projection. Always emit ONBOARDING results (CLEAR included) with `trigger`, `eddRequired`, `sourceEventId`, `sourceVersion`; never PERSON-level events, never the `EDD` pseudo-match.
- Four-eyes on every decision (§5.3 matrix): checker ≠ maker, ≠ assignee/proposer, ≠ earlier-level checker; EDD needs CAMLCO at level 2; `approval.events` carries `checkerRoles` of the current level. Write `audit.events` in the same DB transaction as the change.
- Tipping-off: no customer notification about AML cases, screenings or STRs; the only customer template is `WALLET_RESTRICTED_NOTICE`, opt-in, regulatory instructions only. No narrative in events, notifications, audit or wallet comments.
- PII: never store/log a clear NID or full MSISDN (kernel K2 hash + mask). Officer-typed STR ID numbers are encrypted (`FieldCipher`) and never returned or logged.
- `txn.events` ingestion is batched and idempotent via `ON CONFLICT DO NOTHING` (ADR-02); other consumers use the inbox. Business dates use `CUTOFF.EOD` (Asia/Dhaka).
- Scenario logic = code types; thresholds = data. Transliteration table = data. Seeds are provisional.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-SVC11-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.compliance` (layered: controller → service → repository / client / messaging) — `controller` / `dto` / `service` (business logic, jobs, approval engine, matcher, scenarios, freeze engine, goAML writer, `FieldCipher`, `Hasher`) / `repository` (Spring Data JPA) / `entity` (JPA entities, state machines, enums) / `mapper` / `exception` (problem+json advice) / `client` (`HttpLedgerClient`, `HttpWalletClient`, `HttpLimitsRiskClient`, `HttpAdminClient`; `ObjectStorage` interface with `s3` and `local-fs` implementations) / `messaging` (outbox writer, inbox consumers, batched `txn.events` ingest) / `config` (ActorContext filter, `@RequiresActor`, `Clock` bean); feature sub-packages `lists`, `screening`, `subjects`, `monitoring`, `cases`, `actions`, `reporting`, `approvals`, `evidence`, `refdata` inside each layer. Layering enforced by ArchUnit.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; events consumed twice; ≥ 100-thread concurrency tests on approvals, freeze executor claims, ingestion and re-screen chunks; golden matcher vectors M1–M12 and the goAML STR golden XML; jqwik for scoring symmetry, rollups and lien sizing; log-scan test for NID/MSISDN.

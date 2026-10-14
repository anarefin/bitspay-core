<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# admin-service — agent instructions

You are implementing **admin-service** (SVC-15) of Bits Pay: module `governance` (staff RBAC model, approval inbox, hash-chained audit store, refdata/params/calendar/product switches, retention, activity monitoring) and module `notification` (rules, contacts, BN/EN templates, in-app inbox, channel SPI, deliveries, reminders, logs). This folder is the whole world for this service.

**Release scope (SRS v1.2, CR-ADMIN-1, contractVersion 1.1.0):** MVP product switches enabled = `P2P`, `CASH_IN`, `CASH_OUT`, `MERCHANT_PAYMENT`, `MERCHANT_REFUND`, `FLOAT_TRANSFER`, `REVERSAL`, `BILL_PAY`, `RECHARGE`; all others disabled (BR-GOV-47). Own MVP templates add `BILL_PAYMENT_SUCCESS` / `_FAILED` and `RECHARGE_SUCCESS` / `_FAILED` (BR-NOT-16, WP-CR-1); reminder policy `BILL_DUE` stays disabled. SPEC §10 tags each WP `[MVP]` or `[R1+]` (R1+: WP-5, WP-6, WP-10, WP-18, WP-19, WP-20).

## Read first (every session)
1. `docs/SPEC.md` — the specification (§10 lists work packages WP-1 … WP-21 and WP-CR-1).
2. `docs/contracts/contract.yaml` — what this service provides (incl. the three **inbound topics** it owns) and consumes (pins).
3. `docs/contracts/provided/*` — binding API, event, code and data contracts this service owns.
4. `docs/contracts/consumed/*` — snapshots of everything used from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, maker-checker K5, audit K6, roles K7).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- Offline audit verifier: `java -jar build/libs/admin-service.jar --verify-bundle=<zip>`
- From repo root: `make rebuild svc=admin-service`, `make hybrid svc=admin-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check admin-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Branch `admin-service/<module>/wp-<n>-<slug>` (`common` for shared WPs).
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` and `docs/MODULES.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_admin` only. One outbox `svc_admin.outbox` for both modules. notification tables carry the `notif_` prefix; Redis prefixes `gov:` / `n:` stay disjoint.
- Modules talk only through `<module>.service.<Module>Facade` interfaces (`GovernanceFacade`, `NotificationFacade`) and `<module>.dto` records, enforced by `ArchitectureTest`; no cross-module tables, no cross-module DB transactions. Governance alerts go through `notification.requests` like any sender.
- This service moves no money and calls only wallet-service `GET /v1/wallets/{walletId}` (contact fallback, timeout + circuit breaker).
- **Audit store is append-only:** never UPDATE/DELETE `audit_record`, `chain_seal`, `audit_anchor`; triggers and grants stay. Canonical JSON + hash chain exactly as SPEC §7.3; golden vectors must always pass; never change the algorithm, genesis strings, field list or ordering. One writer per partition (optimistic `chain_head.version`; 0 rows → rollback, no offset commit).
- The approval inbox never decides anything. Every own change is maker-checker; checker ≠ maker, ≠ subject staff, ≠ earlier-level checkers.
- `refdata.events`: never a tombstone; deactivate with `active: false`; `version` + 1 per approved change; key `{type}:{code}`; republish keeps the version.
- Notifications: one message per (sourceKey, recipient, template, channel) — UUIDv5 ids + `INSERT … ON CONFLICT DO NOTHING`; dispatch only rows actually inserted; commit offsets only after the batch TX; every delivery transition is a conditional UPDATE on the expected status.
- Never notify customers for `AML_FREEZE`, `REGULATORY_INSTRUCTION`, `COURT_ORDER` (or their lifts) or from `case.events`; never overwrite a wallet contact's MSISDN/name from `partner.events`; mandatory categories (SECURITY, TRANSACTIONAL, SERVICE, INTERNAL) cannot be opted out.
- MONEY template variables are int64 poisha named `…Poisha`; never pre-formatted; MSISDN variables are masked only by the template formatter.
- Templates, reason codes and product codes declared by other services come **only** from the seed import of `../../docs/global/generated/*.json` (copied at build time). Never hand-add another service's template to `codes.yaml`; a new producer code is data (BN/EN text in `seed/template-texts/`), not a contract change.
- Every write and every audit/log read emits `AUDIT_RECORDED` in the same TX; audit/log reads are audited before data is returned (503 if that fails).
- PII never in logs: mask MSISDN `8801711****00`; never log message bodies, variables or `c14n` (only the `AUDIT_FORWARD` appender).
- Layered dependencies only (controller → service → repository / client / messaging; controllers never touch entities) — `ArchitectureTest` (ArchUnit) enforced.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` (incl. the inbound-topic schemas of `notification.requests`, `approval.events`, `audit.events`) or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-ADMIN-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
Traditional layered (kernel K9 "Layout"): `com.bracits.bitspay.admin` — `common` (`config` ActorContext, `exception` problem, `messaging` outbox, idempotency, `service` maker-checker engine, job leader, `client` Redis) · `governance.{controller, dto, service, repository, entity, mapper, exception, client, messaging, config}` (`service`: `AuditChain`, `CanonicalJson`, `SodPolicy`, `BusinessCalendar`, `AgeingBucket`) · `notification.{controller, dto, service, repository, entity, mapper, exception, client, messaging, config}` (`service`: `TemplateRenderer`, `Formatters`, `SmsSegmentCalculator`, `RuleCondition`, `DeliveryStateMachine`, `ReminderPlanner`, `NotificationIds`; `client`: `ChannelProvider` implementations, `HttpWalletClient`) · each module's facade is `<module>.service.<Module>Facade`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*` (all 123 operations, 7 event schemas); consumer tests from `docs/contracts/consumed/*`; every consumed fixture delivered twice → single effect; ≥ 100-thread concurrency tests on the chain writer, approvals, notification ingest and dispatch; golden audit-chain vectors and golden template samples; tamper-detection suite; log scan for PII.

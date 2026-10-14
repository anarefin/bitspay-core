<!-- Generated from docs/CLAUDE.md of the v6 pack; paths adjusted to the bitspay-core layout. -->
# pricing-service — agent instructions

You are implementing **pricing-service** of Bits Pay: modules `pricing` (fees, VAT, MDR, quote, `fee.rules`, commissions, sharing, AIT, settlement — lead, Dev-6) and `campaign` (campaigns, segments, rewards, clawback — Dev-4, R2). This folder is the whole world for this service.

## Read first (every session)
1. `docs/SPEC.md` — the specification (one clean text; §10 lists work packages per module).
2. `docs/contracts/contract.yaml` — what this service provides and consumes (pins).
3. `docs/contracts/provided/*` — binding API / event / code contracts this service owns, incl. `data/pricing-algorithm.v1.md` and `data/pricing-golden-vectors.v1.json`.
4. `docs/contracts/consumed/*` — snapshots of everything this service uses from others (read-only).
5. `../../docs/global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=pricing-service`, `make hybrid svc=pricing-service`, `make verify`
- Contracts: `../../scripts/contracts.sh check pricing-service`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Stay inside your module: `com.bracits.bitspay.pricing.pricing` (Dev-6) or `com.bracits.bitspay.pricing.campaign` (Dev-4); `common` changes are reviewed by both. Use the other module only via its `<module>.service.<Module>Facade` (and `<module>.dto` records); never touch its tables.
- Contract-first: implement `docs/contracts/provided/*` exactly; consume others only via `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` and `docs/MODULES.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_pricing` only. One outbox `svc_pricing.outbox` for both modules; `payload NULL` (tombstone) only for topic `fee.rules`. Campaign tables are prefixed `campaign_`.
- Money is `long` poisha, rates `int` bps; no `double`/`float`; rounding HALF_EVEN only via `bpsOf`.
- The evaluator follows `pricing-algorithm` v1 exactly; every golden vector must stay green. Never edit a CATALOGUE vector.
- Publish a plan on `fee.rules` only when its version becomes ACTIVE (key `planId`); tombstone on retire; EXPIRED republished with `status: "EXPIRED"`.
- Ledger commands allowed: `post-commission-settlement` (pricing only); `post-campaign-reward` and `post-reversal` of own type-12 rewards with both flags false (campaign only, own ledger client `HttpCampaignLedgerClient`). Never debit a partner wallet.
- Persist `commandId` (and attempt) before every ledger call. 503/timeout → retry the same `commandId` and body. Definitive `REJECTED` → new attempt id `UUIDv5(campaignId, name + ":" + n)` (rewards) or a new settlement id (settlements). Never mark FAILED on an unknown outcome.
- Intent first for rewards: reward row + budget reservation committed before any limits/ledger call; budgets only via conditional UPDATEs; every unpaid attempt that reserved limits gets a durable `:release`.
- `REWARD_GRANTED` always carries all nine fields; `REWARD_CLAWED_BACK` always carries `clawbackMode`; `COMMISSION_SETTLED` carries `txnRef` and `accrualCount`.
- Business dates = `localDate(ts @ Asia/Dhaka − CUTOFF.EOD)`; honour `FEATURE.CAMPAIGN` (422 `SERVICE_DISABLED` before side effects).
- State change + outbox (`fee.rules` / `commission.events` / `campaign.events` / `audit.events` / `approval.events` / `notification.requests`) in ONE DB transaction. Maker ≠ checker; level-2 ≠ level-1; approvals expire after 72 h.
- Consumers idempotent (inbox, DB offsets for campaign `txn.events`, version compare); ignored pricing `txn.events` must not touch the DB.
- PII never in logs; MSISDN, NID, deviceId stored only as K2 HMAC hashes.

## Never change without a change request (`../../docs/global/CHANGE-PROCESS.md`)
- Anything under `docs/contracts/provided/` or `docs/contracts/consumed/`, `contract.yaml` pins, `codes.yaml`, the golden vectors and the algorithm text.
- If a WP seems to need a contract change: stop, write `docs/changes/CR-PRICING-<n>.md` (template in `../../docs/global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.pricing.{pricing,campaign,common}` — layered (global K9): `pricing` and `campaign` each with `controller` / `dto` / `service` / `repository` (Spring Data JPA) / `entity` / `mapper` / `exception` / `client` / `messaging` / `config`; `common` holds shared config, exception, messaging (outbox, inbox, maker-checker engine) and clients. Module facades: `pricing.service.PricingFacade`, `campaign.service.CampaignFacade` (+ `<module>.dto` records); no ports or adapters; `ArchitectureTest` enforces the module and layer rules. Flyway locations `db/migration/{common,pricing,campaign}`.

## Testing expectations
Provider contract tests against `docs/contracts/provided/*`; consumer tests from `docs/contracts/consumed/*`; events consumed twice; ≥ 100-thread concurrency tests on settlement, accrual, budget and executor paths; jqwik properties for every amount computation (bpsOf, shares, rewards, budgets); golden vectors on every build; Salma share examples and S15 reward flow reproduced exactly.

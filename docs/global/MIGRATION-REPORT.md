# Migration Report — v5.0 pack → Service Specs v6 (baseline 1.0.0, 2026-10-13)

## 1. Result

| Pack | SPEC.md lines | Mermaid diagrams | Provided ops | Produced eventTypes | Consumed ops | Consumed event subscriptions | OPEN D-xx tags |
|---|---|---|---|---|---|---|---|
| 01 ledger-service | 2,054 | 13 | 29 | 1 | 0 | 0 | 9 |
| 02 transaction-service | 2,460 | 15 | 30 | 4 | 13 | 3 | 19 |
| 03 wallet-service | 8,538 | 21 | 102 | 9 | 11 | 15 | 12 |
| 05 limits-risk-service | 2,612 | 15 | 46 | 2 | 0 | 15 | 9 |
| 06 pricing-service | 2,882 | 17 | 83 | 5 | 8 | 14 | 14 |
| 07 treasury-service | 5,036 | 20 | 56 | 9 | 14 | 3 | 12 |
| 08 disbursement-service | 2,307 | 15 | 30 | 9 | 12 | 1 | 12 |
| 09 support-service | 5,314 | 14 | 39 | 6 | 19 | 6 | 11 |
| 11 compliance-service | 4,770 | 18 | 74 | 8 | 13 | 14 | 10 |
| 12 finance-ops-service | 6,195 | 19 | 108 | 3 | 11 | 81 | 14 |
| 15 admin-service | 3,282 | 21 | 123 | 1 (+6 inbound-topic types owned) | 1 | 67 | 13 |
| 16 general-ledger-service | 3,803 | 16 | 41 | 6 | 3 | 7 | 5 |
| **Total** | **≈ 49,250** | **204** (+3 in 00-global) | **761** | **63** | **105** | **226** | — |

In total the packs hold 20 topics, 226 consumer-group subscriptions and 105 notification templates, declared by their senders.

## 2. Verification (all run on 2026-10-13)

| Check | Command | Result |
|---|---|---|
| Contract consistency: manifests parse; schemas and examples valid; pins resolve; every `fieldsUsed` path exists in the producer artefact; code sets resolve; uniqueness of topics, operations, prefixes and group ids; rule O2 | `contracts.py check` | **12 packs · 0 errors** · 8 warnings. The warnings are `refdata.events.attributes.*` paths that cannot be proven, because attributes are per-type (admin data contract `refdata-attributes.v1.schema.json`) |
| Mermaid syntax | `node tools/mermaid-check.mjs services/*/SPEC.md 00-global/*.md` (mermaid 11.15) | **207 diagrams · 0 failed** |
| Isolation: no references to other packs' folders, the old catalogue, overlay text, Maven or Helm before the Provenance notes | grep over every SPEC.md and CLAUDE.md | **0 hits** in all 12 packs |
| Audit coverage: every AUD §4 edit id cited in its pack | script over AUD §4.1–4.11 | **263 / 263** |
| Snapshots, stubs and fixtures generated | `contracts.py snapshot all` | 12 packs; `consumed/<producer>/` + `PINS.lock`, WireMock stubs, event fixtures |
| Change-impact drill (scratch copy) | `impact transaction-service "txn.events/TRANSACTION_COMPLETED#amountPoisha"` | 5 impacted (limits-risk, pricing, compliance, finance-ops; admin via `*`); wallet-service correctly **not** impacted |
| Additive change drill | `impact … #terminalId` (new field) | "ADDITIVE (kind B): no consumer impact" |
| CR kind B dry run | `cr new` → `cr analyse` → edit producer → `cr verify` | Adoption Plan = producer only; verify **OK**, only `02-transaction-service` changed |
| CR kind C dry run, with a deliberate scope violation | `cr analyse` (rename `amountPoisha`) → edit producer + 1 consumer + 1 unplanned pack → `cr verify` | verify **failed as intended**: reported "changed OUTSIDE the plan: support-service" and "planned packs not changed yet: pricing, compliance, admin, finance-ops" |

## 3. Coverage

- **Contract audit:** all 263 per-spec edits (AUD §4.1–4.11) are applied and cited. The 5 edits to the standards (AUD §4.13) are folded into the kernel:
  - idempotency retention of 7 days
  - nullable outbox payload
  - DLQ headers
  - k6/Helm/CI removed from scope
- **GL change requests:** CCR-GL-01 to 08 are applied as accepted:
  - the GL pack owns `gl.events`, the CoA and the GL export (GL-01, GL-04);
  - ledger adds the history flag (GL-02) and the optional `reasonCode` on `ledger.changes` (GL-03);
  - finance-ops removed `gl_mapping`, `coa_mapping`, `gl_export`, EOD step 5, the gl-summary endpoint and B-WP-10, and added the `recon.events` additions (GL-04, GL-05);
  - admin carries the GL routing, refdata and templates (GL-06, GL-07; the templates are sent by GL);
  - GL-08 is applied in finance-ops and GL.
- **Catalogue sections:** every section now has one owner; the mapping is in `MIGRATION-SOURCES.md` → "Ownership decisions applied".
- **Open decisions:** 49 of 51 D-ids appear as `OPEN D-xx` tags with their provisional v1.4 values; each pack lists its tags in SPEC §13. Two do not appear:
  - **D-08** (closure payout destination) is recorded as decided in v1.4.
  - **D-47** (login/session audit, SIEM) belongs to the deferred edge/auth layer.

## 4. Review items raised while consolidating (please confirm)

These are judgement calls the pack authors made where the sources were silent or in conflict. Each is also noted in that pack's SPEC §13.

| # | Pack | Item | Why it matters |
|---|---|---|---|
| R1 | ledger | Rejections decided **before** TigerBeetle are persisted in a Postgres `command_rejection` table, so "a REJECTED is final" (D-16). As a result, **commands return 503 while Postgres is down**; the old spec let payments keep flowing. Commands 8 and 13 now journal synchronously for the same reason | Availability trade-off on the hot path |
| R2 | ledger ↔ treasury | Ledger accepts an optional `reasonCode` on `post-emoney-redeem` (CCR-GL-03 derives it from the command body for types 10/11). Treasury does **not** send it yet. GL rule set v1 does not use it | When the GL needs it, raise a kind-D CR to treasury-service. This is a good first exercise of `CHANGE-PROCESS.md` |
| R3 | ledger | The "main callers" of ledger reads are now **enforced allow-lists** (plus general-ledger-service and STAFF) | New readers need a kind-B CR to the ledger |
| R4 | admin | `txn.events` is chained into the audit hash chain **per partition**, with its own chain prefix (OPEN D-05). The sources did not define how the two topics share one chain | Audit-integrity design |
| R5 | transaction | Idempotency is met with a 26 h Redis claim plus a 7-day Postgres look-back. `txn.events` retention is 7 d in the contract but 14 d in the local `topics.csv` | Align the stack config |
| R6 | pricing ↔ wallet | pricing serves `/v1/wallets/{walletId}/offers\|rewards\|points`, which share the `/v1/wallets` prefix with wallet-service | Edge routing (future gateway) must route by full path |
| R7 | wallet | Three staff paths renamed to avoid collisions: `/v1/wallet-config/{key}`, `/v1/partner-documents/{documentId}…`, `/v1/internal/wallet-jobs/{jobName}:run`. Three new reason-code groups (Partner application, Partner change, QR revoke) are tagged OPEN D-32 | Governance seed sign-off |
| R8 | finance-ops ↔ GL | Control-total bucket names (`SYS:<TYPE>`, `TRUST`+`trustIndex`, `WALLET:<t>`) must match on both sides. Refdata code `RETENTION.AUDIT` is needed for `access_log` retention | Confirm with the GL owner and admin seeds |
| R9 | treasury | Source conflict: the catalogue sets `EMONEY_ISSUED.floatRequestId` for counterparty BANK, but in the flows a BANK float return is a redemption. The pack uses OPERATOR | Finance to confirm |
| R10 | all | Packs added provider-owned problem `reason` values and a few operations the old specs implied but did not type: support (~40 reasons), disbursement (10), treasury (cancel and attachment endpoints), compliance (`:retry`, report GETs), admin (approval routes, seed import). Each is listed in its SPEC §13 | Review per pack before WP-1 |
| R11 | support / compliance / disbursement | Additional consumed operations were added because the catalogue requires them, e.g. support's legal-holds read, disbursement's `GET /v1/wallets/{walletId}`, compliance's ledger command lookup | Already pinned and checked; FYI |

## 5. Incidents during generation (resolved)

- **Shared scratchpad collisions:** parallel authoring agents overwrote each other's generic helper scripts in the shared scratchpad. One run wrote the limits-risk OpenAPI into the ledger pack. The ledger pack was regenerated and verified clean (no `/v1/risk` content), and every agent re-checked its own pack for foreign content. No pack file is affected now (the isolation check and `contracts.py check` both pass).
- **Code-set name mismatches:** consumers guessed producer code-set names (`paymentStatus`, `feeBearer`, `reservationState`, …). The names were reconciled to the producers' actual names. `feeBearer` was dropped from producer pins because it is a kernel enum (K3.5). Two features were added to the tool: `reason:<Group>` sets, and per-entry `producer` for code sets owned by another service.
- **Generic ledger pin:** support-service pinned `POST /v1/ledger/commands/{name}`. It was split into the literal `create-hold` and `release-hold` operations that the ledger publishes.
- **Mermaid:** 9 sequence diagrams used `;` inside messages (`;` is a statement separator in Mermaid). They were fixed, and all diagrams now parse.

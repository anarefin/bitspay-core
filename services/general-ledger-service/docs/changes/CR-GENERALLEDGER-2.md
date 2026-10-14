# CR-GENERALLEDGER-2 — MVP: biller liability mapping; remove GL journal export

| Field | Value |
|---|---|
| CR id | CR-GENERALLEDGER-2 |
| Producer (owning pack) | general-ledger-service |
| Requested by | Product owner (MVP scope, 2026-10-14) |
| Kind | C |
| State | Analysed |
| Created | 2026-10-14 |
| Baseline hash | e42134d24c4048dc |

## 1. Motivation
SRS v1.2 (14 Oct 2026) adds the MVP release before R1 and removes every external accounting-system concept from the platform:
- **Withdrawn:** GLD-031 (daily GL journal file), INT-01 (GL journal export) and B-18. UC-13 is renamed "Daily GL close". LED-014 is reworded: "Ledger accounts shall be mapped to the Operator's chart of accounts by the General Ledger service (GLD-006, GLD-013); the real-time view is the GL open-day overlay (GLD-030)." A-37 is reworded: the GL is the system of record for the Operator's books; financial statements are produced from it. The GL keeps the books and produces the trial balance, balance sheet and P&L only.
- **New MVP products:** BIL-011 (internal biller catalogue, simulated biller settlement) and BIL-012 (mobile recharge), UC-16 and UC-17. The ledger adds account type 150 `BILLER_WALLET`, transfer codes 1017 `BILL_PAY_PRINCIPAL` / 1018 `RECHARGE_PRINCIPAL` and commands 18 `post-bill-payment` / 19 `post-recharge` (ledger contract 1.1.0). Wallet adds wallet type `B` (wallet contract 1.1.0). The GL must book them.
- **Slice:** GL-R1a is the MVP slice ([MVP]); GL-R1b is R1+.

## 2. Change (before → after)

**Part 1 — removal of the GL journal file export (breaking).**

| Artefact | Before (1.0.0) | After (2.0.0) |
|---|---|---|
| openapi.yaml | 41 operations, incl. `GET /v1/gl/exports`, `GET /v1/gl/exports/{businessDate}`, `GET /v1/gl/exports/{businessDate}/versions/{n}/file`, `POST /v1/gl/exports/{businessDate}:regenerate`; schemas `GlExport`, `GlExportPage`; tag `Exports` | 37 operations; the four paths, both schemas and the tag removed. `ReasonRequest` is kept (used elsewhere). `info.version` 2.0.0 |
| codes.yaml `codeSets` | `exportStatus` {GENERATING, GENERATED, FAILED, SUPERSEDED}, `exportFormat` {GENERIC_CSV_V1} | removed |
| codes.yaml `problemReasons` | `RANGE_TOO_LARGE` listed `GET /v1/gl/exports`; `DAY_NOT_CLOSED` listed `POST /v1/gl/exports/{businessDate}:regenerate` | those operations removed from the lists |
| codes.yaml `entityTypes` | `GlExport` [REGENERATE], 1 level | removed |
| codes.yaml `notificationTemplates` | `GL_EXPORT_READY`, `GL_EXPORT_FAILED` | removed (also from `contract.yaml → consumes.inboundTopics[notification.requests].templates`) |
| codes.yaml `metrics` | `bitspay_gl_export_last_success_timestamp_seconds` | removed (and alert `GlExportMissing`) |
| data contracts | `gl-export-generic-csv` v1 (`provided/data/gl-export-generic-csv.v1.md`) | file deleted; provides entry removed |
| SPEC / reference DDL | table `gl_export`; `approval_request.entity_type` value `GlExport`; export state machine; `ExportJob` (+ day-close step 8 call); `bitspay.gl.export.*`; §7.10 BR-GL-100…102; ADR-GL-13; WP-9; S-GL9; OPEN G-09; context-diagram node and edge; audit actions `EXPORT_*` | all removed; ADR-GL-13, §7.10, BR-GL-100…102, WP-9, S-GL9, §5.1.32–35 and UC-32…35 (use-cases.html) are left as gaps, numbers not reused |

**Part 2 — MVP biller books (additive).**
- CoA: `2106` E-money liability - billers (LIABILITY, ledger-controlled; all BILLER_WALLET 150), `4108` Fee income - bill payment (FEE 2001 on command 18), `4109` Fee income - recharge (FEE 2001 on command 19). Seed v0: 56 → 59 accounts.
- Rule set v1: `W-150` (tbAccountType 150, any → 2106), `F-FEE-BP` (200 CREDIT, transferCode 2001, commandType 18 → 4108), `F-FEE-RC` (200 CREDIT, 2001, 19 → 4109). 51 → 54 rules. VAT, commission, AIT and reversal legs of 18/19 are covered by the existing transfer-code and command-7 rules.
- Seven-feature MVP slice table (BR-GL-23): Bill payment Dr 2101 / Cr 2106; fee Dr 2101 / Cr 4108; VAT Dr 2101 / Cr 2201. Recharge Dr 2101 / Cr 2106.
- Registry: walletType `B` ↔ 150, bucket `WALLET:B`; codes.yaml `controlTotalBucket` gains `WALLET:B` (additive). Products `BILL_PAY` (18), `RECHARGE` (19) (BR-GL-38). DDL: `gl_posting_rule.command_type` check 1..19; `gl_ledger_account.wallet_type` accepts `B` (SPEC §4.1 and `reference/db/V2__gl_schema.sql`).
- OpenAPI `PostingRule` descriptions (editorial): account types 100..150, transfer codes 1001..1018, command types 1..19. The rule-set example account `4108` (MDR to a new account) became `4110` so it no longer collides with the MVP account.
- SPEC: header/§1 MVP vs R1+; §2 baselined on SRS v1.2 with "· MVP" markers, LED-014 reworded, GLD-031 and INT-01 withdrawn, UC-13 renamed, new rows BIL-011, BIL-012, UC-16/UC-17, A-37; §6 re-pin note; §10 [MVP]/[R1+] tags, GL-R1a [MVP], WP-CR-2; §11 tests and S-GL11; §13 OPEN GL-Q9, GL-Q10; §14 changelog.
- **Seed regeneration deferred to WP-CR-2:** `reference/seed/coa-v0-provisional.csv`, `posting-rules-v1-provisional.yaml`, `posting-universe.json`, `reference/db/V3`/`V4` and the golden vectors' `seedChecksums` are regenerated with the GL reference model against ledger 1.1.0. V01–V36 and both golden days keep their content.

**Re-pin needed (orchestrator; consumes pins not edited here):**
- ledger-service → 1.1.0 for `ledger.changes/LEDGER_TRANSFER_POSTED` (codesUsed `transferCode`, `commandType` "*" now include 1017/1018 and 18/19), `GET /v1/ledger/accounts/{id}/balance` (codesUsed `accountType` explicit values [100..140] → add 150), and `consumes.codes` `accountType` / `transferCode` / `commandType`.
- wallet-service → 1.1.0 for `wallet.events/WALLET_UPSERTED` (codesUsed `walletType` [C, A, D, M, I] → add `B`).

## 3. Artefacts touched
<!-- one per line, impact syntax: "METHOD /path[#field]" | <topic>/<EVENT_TYPE>[#field] | codes/<set>[#value] | data/<id> | internal -->
- "GET /v1/gl/exports"
- "GET /v1/gl/exports/{businessDate}"
- "GET /v1/gl/exports/{businessDate}/versions/{n}/file"
- "POST /v1/gl/exports/{businessDate}:regenerate"
- data/gl-export-generic-csv
- codes/exportStatus
- codes/exportFormat
- codes/notificationTemplates#GL_EXPORT_READY
- codes/notificationTemplates#GL_EXPORT_FAILED
- codes/metrics#bitspay_gl_export_last_success_timestamp_seconds
- codes/controlTotalBucket#WALLET:B
- "POST /v1/gl/rule-sets"
- "POST /v1/gl/rule-sets:validate"

Also removed, not listed as a bullet because `contracts.py impact` currently fails on this pack's `entityTypes` shape (TypeError in `code_values`): `codes/entityTypes#GlExport`. No `gl.events` type changes.

## 4. Proposed versions
| Artefact | From | To |
|---|---|---|
| contractVersion | 1.0.0 | 2.0.0 |
| openapi `info.version` | 1.0.0 | 2.0.0 (path major stays `/v1`: the removed operations have no consumers, so there is no dual-run) |
| data `gl-export-generic-csv` | 1 | removed |

## 5. Adoption Plan
*(generated by `contracts.py cr analyse` on 2026-10-14 — re-run after changing §3)*

### 5.1 Producer — general-ledger-service (`services/16-general-ledger-service/`)

- [ ] `contracts/provided/*` — `"GET /v1/gl/exports"`; `"GET /v1/gl/exports/{businessDate}"`; `"GET /v1/gl/exports/{businessDate}/versions/{n}/file"`; `"POST /v1/gl/exports/{businessDate}:regenerate"`; `data/gl-export-generic-csv`; `codes/exportStatus`; `codes/exportFormat`; `codes/notificationTemplates#GL_EXPORT_READY`; `codes/notificationTemplates#GL_EXPORT_FAILED`; `codes/metrics#bitspay_gl_export_last_success_timestamp_seconds`; `codes/controlTotalBucket#WALLET:B`; `"POST /v1/gl/rule-sets"`; `"POST /v1/gl/rule-sets:validate"`
- [ ] `SPEC.md` §5 (tables + examples), §3.1 edge labels, §7 rules, §11 tests as affected
- [ ] `SPEC.md` §10: add **WP-CR-GENERALLEDGER-2**
- [ ] `contracts/contract.yaml` `contractVersion` bump (MAJOR (keep old major side by side))
- [ ] `SPEC.md` §14 changelog row

### 5.2 Impacted consumers (0)

None — no other pack reads the changed artefacts/fields. ⚠ Kind C declared but zero impact: consider reclassifying as B.

### 5.3 Not impacted (0) — do not open these packs


## 6. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Producer owner | Ahmad Naqibul Arefin | Approved | 2026-10-14 |

## 7. Implementation
| Service | WP | MR | Merged |
|---|---|---|---|
| general-ledger-service | WP-CR-2 | — | — |

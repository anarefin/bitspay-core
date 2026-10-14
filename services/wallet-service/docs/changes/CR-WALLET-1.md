# CR-WALLET-1 — MVP: BILLER partner type, wallet type B and biller catalogue

| Field | Value |
|---|---|
| CR id | CR-WALLET-1 |
| Producer (owning pack) | wallet-service |
| Requested by | Product owner (MVP scope, 2026-10-14) |
| Kind | B |
| State | Analysed |
| Created | 2026-10-14 |
| Baseline hash | 25d9d1190aa9d2a4 |

## 1. Motivation
SRS v1.2 adds the MVP release (before R1) with bill payment against an **internal biller catalogue** and mobile recharge, both without any external biller or telco call (A-41): BIL-011 (internal biller catalogue and simulated biller settlement), BIL-012 (mobile recharge via the operator catalogue with MSISDN / prefix validation), BIL-008 (configurable biller list, categories, logos, fee bearer, limits), BIL-003 / BIL-004 (amount rules, MNO coverage), use cases UC-16 and UC-17; open decisions B-25 (seed catalogue sign-off) and B-26 (MVP fee / limit values). transaction-service (`BILL_PAY` command 18, `RECHARGE` command 19) must credit a per-biller e-money wallet (ledger account type 150 `BILLER_WALLET`, owner type 6 `BILLER`, CR-LEDGER-1) and validate references, amounts and MSISDN prefixes on the hot path. wallet-service is the system of record for every wallet holder and partner, so the partner module owns billers and their catalogue.

## 2. Change (before → after)
All changes are additive; no field, operation, value or rule consumers rely on is removed or tightened.

- `codes/walletType`: `C A D M I` → `+ B` (name BILLER, ledgerAccountType `BILLER_WALLET`, ownerType `BILLER`). `codes/ownerType`: `+ BILLER`.
- `codes/partnerType`: `+ BILLER`; `codes/partnerSubType`: `+ UTILITY, EDUCATION, GOVT_FEE, INTERNET_TV, MNO` (partnerType BILLER).
- `codes/categoryCode`: `+ 501 BILLER_UTILITY, 502 BILLER_EDUCATION, 503 BILLER_GOVT_FEE, 504 BILLER_INTERNET_TV, 505 BILLER_MNO` (44 → 49 values).
- New code sets `billerCategory` (UTILITY_ELECTRICITY, UTILITY_GAS, UTILITY_WATER, INTERNET, TV, EDUCATION, GOVT_FEE, MOBILE_PREPAID, MOBILE_POSTPAID), `billerAmountMode` (ENQUIRY, FIXED, OPEN), `billerFeeBearer` (PAYER, BILLER), `rechargeType` (PREPAID, POSTPAID).
- New problem reasons `409 STATE_CONFLICT DUPLICATE_BILLER_CODE` and `MSISDN_PREFIX_TAKEN` on `POST /v1/partner-applications/{applicationId}:submit` and `POST /v1/partners/{partnerId}/profile-changes`.
- New business prefix `B` (partnerCode of a BILLER, `B{8-digit sequence}{Luhn}`); metric `bitspay_partner_biller_cache_writes_total{source,result}`.
- OpenAPI (1.0.0 → 1.1.0): every `partnerType` / `ownerType` / `walletTypeName` enum `+ BILLER`, every `walletType` enum `+ B`, every partner `subType` enum `+` the five biller sub-types, every `partnerCode` pattern `^[AMDI][0-9]{9}$` → `^[AMDIB][0-9]{9}$` (wider). New schemas `BillerProfileInput`, `Biller`. New optional `PartnerForm.biller` (request; required only for the new type BILLER) and `PartnerDetail.biller` (response). `changes.biller` documented as an APPROVAL field of profile changes (loose object, description only). New operations `GET /v1/billers` (filters category, subType, status, msisdnPrefix, q; paged) and `GET /v1/billers/{billerId}` (x-release MVP).
- `partner.events/PARTNER_UPSERTED` v1: optional `biller` object (null / absent for non-billers) with billerCode, nameEn, nameBn, category, logoKey, referenceLabelEn, referenceLabelBn, referencePattern, amountMode, fixedAmountPoisha, minAmountPoisha, maxAmountPoisha, feeBearer, msisdnPrefixes, rechargeTypes, denominationsPoisha (schema + `examples`); enum / pattern widenings as above. Before: `{…20 fields, tinPresent}` → after: `{…20 fields, tinPresent, biller?}`.
- `wallet.events/WALLET_UPSERTED` v1: `ownerType + BILLER`, `walletType + B`.
- `data/wallet-status-cache` v1: `walletTypeCode` may be `B`; `categoryCode` 501..505 (format unchanged; readers already treat unknown codes safely).
- New data contract `data/biller-catalogue-cache` v1 (redis-format, `provided/data/biller-catalogue-cache.v1.md`): `biller:{billerId}` JSON `{schema, billerId, version, billerCode, partnerCode, subType, category, categoryCode, nameEn, nameBn, logoKey, status, walletId, referenceLabelEn, referenceLabelBn, referencePattern, amountMode, fixedAmountPoisha, minAmountPoisha, maxAmountPoisha, feeBearer, msisdnPrefixes, rechargeTypes, denominationsPoisha, updatedAt}` written by Lua CAS on `version`; `biller:mno-prefix:{prefix}` → billerId; `biller:meta`. Writers: partner write-through after commit + `biller-cache-refresh` job (cache-loader role). Reader fallback `GET /v1/billers/{billerId}` / `?msisdnPrefix=`.
- Internal (SPEC): tables `partner_biller_profile`, `partner_biller_msisdn_prefix`; CHECKs of `wallet.owner_type` / `wallet.wallet_type` / `partner.partner_type` / `partner.partner_code` extended; partner V4 migration with biller seeds (category map, hierarchy rule, chain `BILLER_STD`, checklist) and 11 seed DRAFT applications (DESCO, DPDC, TITAS, WASA, BTCL-INT, SCHOOL-DEMO, GP, ROBI, AIRTEL, BANGLALINK, TELETALK); rules BR-PAR-80..89 (validation, submit, screening without KYC tiers, prefix uniqueness, profile changes via maker-checker, activation of the `B` wallet like a merchant's 130, `msisdn_scope 'B'`, cache writer, refresh, read APIs); flow F10; §2 baseline SRS v1.2 with MVP markers; §10 `[MVP]` / `[R1+]` tags and WP-CR-1; §11 tests; §13 B-25, B-26, deferrals; §14 changelog.

## 3. Artefacts touched
<!-- one per line, impact syntax: "METHOD /path[#field]" | <topic>/<EVENT_TYPE>[#field] | codes/<set>[#value] | data/<id> | internal -->
- "GET /v1/billers"
- "GET /v1/billers/{billerId}"
- "POST /v1/partner-applications#req.formData.biller"
- "PATCH /v1/partner-applications/{applicationId}#req.formData.biller"
- "POST /v1/partner-applications/{applicationId}:submit#problem.reason"
- "POST /v1/partners/{partnerId}/profile-changes#req.changes"
- "GET /v1/partners/{partnerId}#res.biller"
- partner.events/PARTNER_UPSERTED#biller
- codes/walletType#B
- codes/ownerType#BILLER
- codes/partnerType#BILLER
- codes/partnerSubType
- codes/categoryCode
- codes/billerCategory
- codes/billerAmountMode
- codes/billerFeeBearer
- codes/rechargeType
- data/wallet-status-cache
- data/biller-catalogue-cache
- codes/txnRefPrefixes#B
- codes/problemReasons

Enum and pattern widenings on existing fields (`walletType`, `ownerType`, `partnerType`, `subType`, `partnerCode` in the OpenAPI and in `PARTNER_UPSERTED` / `WALLET_UPSERTED`) are carried by the code-set lines above (new values in response / event fields are kind B, kernel K1); consumers listed by `impact` with `"*"` or the whole set are review-only (tolerant readers). transaction-service already pins `data/biller-catalogue-cache` v1 at 1.1.0 (CR-TRANSACTION-1); every field it lists exists in this contract.

## 4. Proposed versions
| Artefact | From | To |
|---|---|---|
| contractVersion | 1.0.0 | 1.1.0 |
| openapi.yaml `info.version` | 1.0.0 | 1.1.0 |
| PARTNER_UPSERTED / WALLET_UPSERTED eventVersion | 1 | 1 (additive) |
| data `wallet-status-cache` | v1 | v1 (additive) |
| data `biller-catalogue-cache` | — | v1 (new) |

## 5. Adoption Plan
*(generated by `contracts.py cr analyse` on 2026-10-14 — re-run after changing §3)*

### 5.1 Producer — wallet-service (`services/03-wallet-service/`)

- [ ] `contracts/provided/*` — `"GET /v1/billers"`; `"GET /v1/billers/{billerId}"`; `"POST /v1/partner-applications#req.formData.biller"`; `"PATCH /v1/partner-applications/{applicationId}#req.formData.biller"`; `"POST /v1/partner-applications/{applicationId}:submit#problem.reason"`; `"POST /v1/partners/{partnerId}/profile-changes#req.changes"`; `"GET /v1/partners/{partnerId}#res.biller"`; `partner.events/PARTNER_UPSERTED#biller`; `codes/walletType#B`; `codes/ownerType#BILLER`; `codes/partnerType#BILLER`; `codes/partnerSubType`; `codes/categoryCode`; `codes/billerCategory`; `codes/billerAmountMode`; `codes/billerFeeBearer`; `codes/rechargeType`; `data/wallet-status-cache`; `data/biller-catalogue-cache`; `codes/txnRefPrefixes#B`; `codes/problemReasons`
- [ ] `SPEC.md` §5 (tables + examples), §3.1 edge labels, §7 rules, §11 tests as affected
- [ ] `SPEC.md` §10: add **WP-CR-WALLET-1**
- [ ] `contracts/contract.yaml` `contractVersion` bump (MINOR)
- [ ] `SPEC.md` §14 changelog row

### 5.2 Impacted consumers (5)

- [ ] **disbursement-service** (`services/08-disbursement-service/`): codes walletType — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot disbursement-service`
  - update `SPEC.md` §6 subsection for wallet-service + rules/WPs/tests that use the matched fields; add WP-CR-WALLET-1; changelog row
- [ ] **finance-ops-service** (`services/12-finance-ops-service/`): events partner.events/PARTNER_UPSERTED — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot finance-ops-service`
  - update `SPEC.md` §6 subsection for wallet-service + rules/WPs/tests that use the matched fields; add WP-CR-WALLET-1; changelog row
- [ ] **general-ledger-service** (`services/16-general-ledger-service/`): codes walletType — matched ['C', 'A', 'D', 'M', 'I', 'B']
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot general-ledger-service`
  - update `SPEC.md` §6 subsection for wallet-service + rules/WPs/tests that use the matched fields; add WP-CR-WALLET-1; changelog row
- [ ] **transaction-service** (`services/02-transaction-service/`): codes walletType — matched *; codes categoryCode — matched *; data wallet-status-cache — matched bucket, key, field, value.version, value.statusCode, value.kycTier, value.walletTypeCode, value.categoryCode, value.flags, negativeCache; data biller-catalogue-cache — matched biller:{billerId}, biller:mno-prefix:{prefix}, biller:meta.state, schema, billerId, billerCode, subType, category, walletId, referencePattern, amountMode, fixedAmountPoisha, minAmountPoisha, maxAmountPoisha, status, msisdnPrefixes, rechargeTypes
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot transaction-service`
  - update `SPEC.md` §6 subsection for wallet-service + rules/WPs/tests that use the matched fields; add WP-CR-WALLET-1; changelog row
- [ ] **treasury-service** (`services/07-treasury-service/`): codes partnerSubType — matched ['SUPER_AGENT']
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot treasury-service`
  - update `SPEC.md` §6 subsection for wallet-service + rules/WPs/tests that use the matched fields; add WP-CR-WALLET-1; changelog row

⚠ Kind B declared but consumers are impacted — reclassify as C.

### 5.3 Not impacted (7) — do not open these packs

- admin-service: events partner.events/PARTNER_UPSERTED (does not read the changed field)
- compliance-service: events partner.events/PARTNER_UPSERTED (does not read the changed field)
- limits-risk-service: events partner.events/PARTNER_UPSERTED (does not read the changed field)
- pricing-service: events partner.events/PARTNER_UPSERTED (does not read the changed field); codes partnerType (does not read the changed field)

## 6. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Producer owner | Ahmad Naqibul Arefin | Approved | 2026-10-14 |

## 7. Implementation
| Service | WP | MR | Merged |
|---|---|---|---|
| wallet-service | WP-CR-1 | — | — |

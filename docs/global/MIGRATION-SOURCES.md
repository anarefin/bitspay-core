# Migration Sources — where each v6 pack comes from

This file records how the v6 packs were consolidated from the v5.0 pack. It is the authoring brief for the baseline (1.0.0) and stays here as provenance. **After the baseline it is history**: all later changes follow `CHANGE-PROCESS.md`.

Paths are relative to the workspace root `Bits Pay/`. They use these abbreviations:

| Short | Path |
|---|---|
| CAT | `Dev Plan v5.0/03-Contract-Catalogue-v1.4.md` (v1.4 = contract truth; it already contains the contract-audit fixes) |
| AUD | `Dev Plan v5.0/contract-audit/09-Contract-Audit.md` (§4 = per-spec edit lists the old specs never received) |
| DEC | `Dev Plan v5.0/contract-audit/decisions.md` (D-01..D-51) |
| FND | `Dev Plan v5.0/contract-audit/findings/<svc>.md` · SHT = `…/sheets/<svc>.md` (per-service contract sheets) |
| GLA | `general ledger/03-Contract-Catalogue-GL-Addendum.md` (CCR-GL-01..08 — **applied** in v6) |
| GLI | `general ledger/09-Impact-on-Existing-Services.md` |
| STK | `Dev Plan v5.0/06-Local-Stack-Docker-Compose.md` (mem_limit, profiles, env, topics, group ids) |
| SRS | `Bits_Pay_SRS_v1.0_Draft.docx` (`textutil -convert txt -stdout <file>`) · ARC = `Bits Pay-Architecture-Data-Flow.docx` |

**Precedence when sources disagree:**
1. GLA (for the items it touches)
2. CAT v1.4
3. AUD §4 edits
4. the old spec body

v5.0 overlay rules always replace the base text:
- Gradle, not Maven
- schema `svc_<name>`
- 5k TPS
- no Helm, CI, E2E or k6 in this phase
- no Spring Modulith
- no sharding

## Per-pack sources

| Pack | Old spec | CAT slices (line ranges) | AUD §4 | Other |
|---|---|---|---|---|
| 01 ledger | `Dev Plan v5.0/services/SVC-01-ledger-service.md` | §2 252–1035; `ledger.changes` 2992–3027; Hold reason group in §8.4 (4076–4096) | 926–942 | GLA 25–50, 190–199 (CCR-GL-02 history flag, GL as caller, GL-03 `reasonCode`); GLI 20–35 |
| 02 transaction | `…/SVC-02-transaction-service.md` | §3 1036–1374; `txn.events` 2544–2671; §1.4 problem extensions it returns (143–223: `transaction`, limit fields, `walletId`/`walletStatus`, `remainingPoisha`); §1.5 product codes 224–251; Reversal and Merchant-refund reason groups (§8.4); consumes the §6.2/6.3 pricing algorithm (2338–2380) | 943–973 | — |
| 03 wallet (wallet + partner) | `…/SVC-03-wallet-service.md` | §4 1375–1940; `wallet.events` 2672–2712; `customer.events` 2713–2777; `partner.events` 2778–2842; §12.3.1–12.3.2 5326–5382; templates C1 4321–4341 and C2 4342–4364; §8.4 groups Wallet status, Partner status, KYC, Customer profile, Wallet flag; §13.6 | 974–1006 | — |
| 05 limits-risk | `…/SVC-05-limits-risk-service.md` | §5 1941–2257; `risk.alerts` 2920–2968; `blacklist.events` 2969–2991; §8.4 Blacklist-entry group | 1007–1028 | — |
| 06 pricing (pricing + campaign) | `…/SVC-06-pricing-service.md` | §6 2258–2465 (PlanJson, algorithm, golden vectors become data contracts); `fee.rules` 2843–2868; `commission.events` 2869–2919; `campaign.events` 3441–3485; templates C6 4489–4524 | 1029–1056 | — |
| 07 treasury | `…/SVC-07-treasury-service.md` | `treasury.events` 3028–3288; templates C3 4365–4417; §8.4 groups E-money redemption and Manual journal | 1057–1078 | GLI 68–71 (no change) |
| 08 disbursement | `…/SVC-08-disbursement-service.md` | `disbursement.events` 3289–3440; templates C4 4418–4458; problem extensions `batch`, `paymentRequest` (§1.4.1) | 1079–1101 | — |
| 09 support | `…/SVC-09-support-service.md` | `support.events` 3486–3648; templates C5 4459–4488 | 1102–1125 | — |
| 11 compliance | `…/SVC-11-compliance-service.md` | `case.events` 3649–3792; templates C7 4525–4565; §8.4 Risk-regrade group | 1126–1153 | — |
| 12 finance-ops (reconciliation + reporting) | `…/SVC-12-finance-ops-service.md` | §11.1 4703–4943; §11.3 5018–5147; `recon.events` 3793–3852; §12.3.3–12.3.4 5383–5447; templates C8 4566–4616 | 1154–1192 | GLA 200–227 (recon.events additions, GL-05), 288–303 (gl-summary removed, GL-04); GLI 36–60 (CoA mapping, GL export, EOD step 5 and B-WP-10 **move to GL**) |
| 15 admin (governance + notification) | `…/SVC-15-admin-service.md` | `notification.requests` 3853–3933, `approval.events` 3934–3970, `audit.events` 3971–4006 (**inbound topics**, K4.4); `refdata.events` 4007–4028; §8.4 master list (as seed only), §8.5 4097–4130; §8.6 4131–4163 + groups A 4164–4281, B 4282–4320, C9 4617–4650; §11.2 4944–5017; §11.4 5148–5247 | 1193–1221 | GLA 228–273 (routing, refdata GL-06, templates GL-07); GLI 61–67 |
| 16 general-ledger | `general ledger/services/SVC-16-general-ledger-service.md` | GLA (all), §11.5 GLA 304–389 | — | `general ledger/components/**` (openapi, schemas, golden, fixtures, stubs, seed, db) reused as-is |

**Every pack** also reads:
- STK (its compose service, `mem_limit`, env)
- the CAT §12.1 consumer-group table (5250–5289)
- CAT §7.2 (2509–2537) for topic metadata of the topics it produces and the events it consumes
- the DEC rows that its AUD §4 entries cite

## Ownership decisions applied (how the central registries were split)

| Catalogue item | v6 owner / location |
|---|---|
| §0, §0.1, §1.1–1.3, §1.4 code list + generic problem body, §1.5 rule, §7.1, §8.1 pattern, §8.2 rules, §8.3 roles, §12.1 pattern, §12.2, §13.3–13.4 | Kernel `GLOBAL-CONVENTIONS.md` |
| §1.4.1 extension members and the registered `reason` table | Each provider's OpenAPI + `codes.yaml` (`problemReasons`, `problemExtensions`) |
| §1.5 product table | Owners' `codes.yaml → productCodes`; readers of `FEATURE.*` declare `consumes.refdata` |
| §2.3/§2.4 per-caller `commandId` derivations and allowed callers | Ledger keeps the **input rules and the allowed-caller policy** (its own authorisation). Each caller restates its own derivation in SPEC §6 |
| §3.1 reference prefixes of other owners | Each minting owner's `codes.yaml → txnRefPrefixes` (uniqueness checked by the tool) |
| §4.1 codes, §4.1.1 category codes, §4.2 Redis format | wallet: `codes.yaml` code sets + `provided/data/wallet-status-cache.v1.md` |
| §6.1 PlanJson, §6.2 algorithm, §6.3 golden vectors | pricing: `fee.rules` schema + `provided/data/pricing-algorithm.v1.md` + `provided/data/pricing-golden-vectors.v1.json` |
| §7.2 topic registry (consumer columns) | Producers keep key, partitions, compaction and tombstones. Consumers declare themselves in `contract.yaml` |
| §8.1 entityType table | Each service's `codes.yaml → entityTypes` |
| §8.4 reason-code groups | The service whose field carries the code: `codes.yaml → reasonCodes`. admin-service seeds `REASON_CODE` refdata from the generated index |
| §8.5 refdata types and reserved `SYSTEM_PARAM` namespaces | admin-service (`refdata.events` schema + per-type attribute schemas). Readers list `consumes.refdata` |
| §8.6 categories; §8.6.1 groups A and B | admin-service (notification) |
| §8.6.1 groups C1–C9, GL-07 | The sending service's `codes.yaml → notificationTemplates` (variables copied exactly) |
| §9 registry, §12.1 group-id table | Generated into `SYSTEM-CONTEXT.md` and `DEPENDENCY-INDEX.md` |
| §11.x back-office reads, §12.3 test operations | The owning service's OpenAPI (`x-audience`) |

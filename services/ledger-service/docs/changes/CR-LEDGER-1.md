# CR-LEDGER-1 — MVP: biller account type 150 and bill/recharge commands

| Field | Value |
|---|---|
| CR id | CR-LEDGER-1 |
| Producer (owning pack) | ledger-service |
| Requested by | Product owner (MVP scope, 2026-10-14) |
| Kind | B |
| State | Analysed |
| Created | 2026-10-14 |
| Baseline hash | 9972b68b615192e2 |

## 1. Motivation
SRS v1.2 (14 Oct 2026) adds an MVP release before R1 with bill payment against an internal biller catalogue (**BIL-011**) and mobile recharge via the operator catalogue (**BIL-012**), both with a simulated provider and no external biller or telco call (assumption **A-41**). Each biller (including each MNO) is a partner of type `BILLER` with one settlement wallet (wallet type `B`). The ledger needs an account type for that wallet and one command per product so that transaction-service can move money customer → biller wallet, and reverse it when the simulated provider rejects. Ledger rows LED-001..011, LED-015, LED-018, LED-019 are delivered by the MVP; LED-014 is reworded in v1.2 (CoA mapping by general-ledger-service, GLD-006/013/030).

## 2. Change (before → after)
All changes are additive; no field, value or operation is removed or tightened.

| Artefact | Before | After |
|---|---|---|
| `codes.yaml` `accountType` | 100–140 wallets, 200–910 system | + `{code: 150, name: BILLER_WALLET, normalSide: CREDIT, tbFlags: [debits_must_not_exceed_credits, history], onePer: biller, creatableViaApi: true, ownerType: BILLER}` |
| `codes.yaml` `ownerType` | 1–5, 9 | + `{code: 6, name: BILLER, accountTypes: [150]}` |
| `codes.yaml` `transferCode` | business codes 1001–1016, 2001–2004 | + `1017 BILL_PAY_PRINCIPAL`, `1018 RECHARGE_PRINCIPAL` (business range 1001–1018) |
| `codes.yaml` `commandType` | 1–17 | + `{code: 18, name: post-bill-payment, pattern: linked, principalCode: 1017, lane: online}`, `{code: 19, name: post-recharge, pattern: linked, principalCode: 1018, lane: online}` |
| `codes.yaml` `rejectionDetailToken` `NOT_REVERSIBLE` | original not in {1-6, 8, 12} | original not in {1-6, 8, 12, 18, 19} (reversible set grows) |
| `codes.yaml` `feeBearer`, `commissionSource` descriptions | "payment commands 1-6" | "payment commands 1-6, 18, 19" |
| openapi | 29 operations | + `POST /v1/ledger/commands/post-bill-payment` (x-command-type 18) and `POST /v1/ledger/commands/post-recharge` (19): request `PaymentCommandRequest`, response `CommandResponse` (as `post-merchant-payment`), guard 100 → 150, `x-actors` SERVICE `transaction-service`, same rejection codes |
| openapi `POST /v1/ledger/accounts` | `accountType` enum without 150; `ownerType` enum without BILLER; wallet-service rule "wallet types 100-140" | + `BILLER_WALLET`, + `BILLER` (BILLER↔150); rule "wallet types 100-140, 150" |
| openapi `ReversalCommandRequest.originalCommandId` | type in {1-6, 8, 12} | type in {1-6, 8, 12, 18, 19} |
| openapi `commandType` (`GET /v1/ledger/commands/{commandId}`, `GET …/transfers`) | maximum 17 | maximum 19 |
| openapi `GET /v1/ledger/system-balance-sheet` `byWalletType` | one per wallet type 100-140 | one per wallet type 100-150 (example adds `BILLER_WALLET`) |
| `ledger.changes/LEDGER_TRANSFER_POSTED` v1 | `commandType` max 17; codes 1001-1016 | `commandType` max 19; codes 1001-1018 (new values only; no new version) |
| `data/transfer-id-derivation` v1 | leg table row "1–6 payments" | "1–6, 18, 19 payments" (algorithm unchanged) |
| SPEC rules | — | BR-01-71 (commands 18/19), BR-01-72 (BILLER_WALLET 150), BR-01-73 (reversal of 18/19); BR-01-40 reversible set extended; §5.1.5 guards 18: 100 → 150, 19: 100 → 150 |

Request example (command 18):
```json
{ "commandId": "0192f3e2-0000-7000-8000-000000000001", "txnRef": "BP26101400K7M2Q9XA",
  "fromAccountId": "0192f2aa-0000-7000-8000-00000000a001", "toAccountId": "0192f2ee-0000-7000-8000-00000000e006",
  "amountPoisha": 120000,
  "pricing": { "feePoisha": 500, "vatPoisha": 75, "feeBearer": "PAYER", "commissionPoisha": 0, "commissionSource": null,
               "commissionBeneficiaryAccountId": null, "aitPoisha": 0 },
  "constraints": null, "metadata": { "channel": "APP", "initiatorActorId": "0192f1bb-0000-7000-8000-000000000001" } }
```

## 3. Artefacts touched
<!-- one per line, impact syntax: "METHOD /path[#field]" | <topic>/<EVENT_TYPE>[#field] | codes/<set>[#value] | data/<id> | internal -->
- "POST /v1/ledger/commands/post-bill-payment"
- "POST /v1/ledger/commands/post-recharge"
- "POST /v1/ledger/accounts#req.accountType"
- "POST /v1/ledger/accounts#req.ownerType"
- "POST /v1/ledger/commands/post-reversal#req.originalCommandId"
- "GET /v1/ledger/commands/{commandId}#res.transfers[].commandType"
- "GET /v1/ledger/accounts/{id}/transfers#res.items[].commandType"
- "GET /v1/ledger/system-balance-sheet#res.byWalletType"
- ledger.changes/LEDGER_TRANSFER_POSTED#commandType
- ledger.changes/LEDGER_TRANSFER_POSTED#code
- codes/accountType#BILLER_WALLET
- codes/ownerType#BILLER
- codes/transferCode#BILL_PAY_PRINCIPAL
- codes/transferCode#RECHARGE_PRINCIPAL
- codes/commandType#post-bill-payment
- codes/commandType#post-recharge
- codes/rejectionDetailToken#NOT_REVERSIBLE
- data/transfer-id-derivation

## 4. Proposed versions
| Artefact | From | To |
|---|---|---|
| contractVersion | 1.0.0 | 1.1.0 |
| openapi `info.version` | 1.0.0 | 1.1.0 |
| `LEDGER_TRANSFER_POSTED` eventVersion | 1 | 1 (additive values only) |
| `transfer-id-derivation` data contract | 1 | 1 (algorithm unchanged) |

## 5. Adoption Plan
*(generated by `contracts.py cr analyse` on 2026-10-14 — re-run after changing §3)*

### 5.1 Producer — ledger-service (`services/01-ledger-service/`)

- [ ] `contracts/provided/*` — `"POST /v1/ledger/commands/post-bill-payment"`; `"POST /v1/ledger/commands/post-recharge"`; `"POST /v1/ledger/accounts#req.accountType"`; `"POST /v1/ledger/accounts#req.ownerType"`; `"POST /v1/ledger/commands/post-reversal#req.originalCommandId"`; `"GET /v1/ledger/commands/{commandId}#res.transfers[].commandType"`; `"GET /v1/ledger/accounts/{id}/transfers#res.items[].commandType"`; `"GET /v1/ledger/system-balance-sheet#res.byWalletType"`; `ledger.changes/LEDGER_TRANSFER_POSTED#commandType`; `ledger.changes/LEDGER_TRANSFER_POSTED#code`; `codes/accountType#BILLER_WALLET`; `codes/ownerType#BILLER`; `codes/transferCode#BILL_PAY_PRINCIPAL`; `codes/transferCode#RECHARGE_PRINCIPAL`; `codes/commandType#post-bill-payment`; `codes/commandType#post-recharge`; `codes/rejectionDetailToken#NOT_REVERSIBLE`; `data/transfer-id-derivation`
- [ ] `SPEC.md` §5 (tables + examples), §3.1 edge labels, §7 rules, §11 tests as affected
- [ ] `SPEC.md` §10: add **WP-CR-LEDGER-1**
- [ ] `contracts/contract.yaml` `contractVersion` bump (MINOR)
- [ ] `SPEC.md` §14 changelog row

### 5.2 Impacted consumers (3)

- [ ] **finance-ops-service** (`services/12-finance-ops-service/`): events ledger.changes/LEDGER_TRANSFER_POSTED — matched commandType; events ledger.changes/LEDGER_TRANSFER_POSTED — matched code
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot finance-ops-service`
  - update `SPEC.md` §6 subsection for ledger-service + rules/WPs/tests that use the matched fields; add WP-CR-LEDGER-1; changelog row
- [ ] **general-ledger-service** (`services/16-general-ledger-service/`): events ledger.changes/LEDGER_TRANSFER_POSTED — matched commandType; events ledger.changes/LEDGER_TRANSFER_POSTED — matched code; codes accountType — matched *; codes transferCode — matched *; codes transferCode — matched *; codes commandType — matched *; codes commandType — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot general-ledger-service`
  - update `SPEC.md` §6 subsection for ledger-service + rules/WPs/tests that use the matched fields; add WP-CR-LEDGER-1; changelog row
- [ ] **transaction-service** (`services/02-transaction-service/`): codes rejectionDetailToken — matched ['NOT_REVERSIBLE', 'ACCOUNT_TYPE_MISMATCH', 'id_already_failed']
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot transaction-service`
  - update `SPEC.md` §6 subsection for ledger-service + rules/WPs/tests that use the matched fields; add WP-CR-LEDGER-1; changelog row

⚠ Kind B declared but consumers are impacted — reclassify as C.

### 5.3 Not impacted (2) — do not open these packs

- disbursement-service: codes rejectionDetailToken (does not read the changed field)
- treasury-service: events ledger.changes/LEDGER_TRANSFER_POSTED (does not read the changed field); events ledger.changes/LEDGER_TRANSFER_POSTED (does not read the changed field)

## 6. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Producer owner | Ahmad Naqibul Arefin | Approved | 2026-10-14 |

## 7. Implementation
| Service | WP | MR | Merged |
|---|---|---|---|
| ledger-service | WP-CR-1 | — | — |

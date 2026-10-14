# CR-TRANSACTION-1 — MVP: BILL_PAY and RECHARGE products with simulated biller

| Field | Value |
|---|---|
| CR id | CR-TRANSACTION-1 |
| Producer (owning pack) | transaction-service |
| Requested by | Product owner (MVP scope, 2026-10-14) |
| Kind | B |
| State | Analysed |
| Created | 2026-10-14 |
| Baseline hash | d2d66e47c5a4831e |

## 1. Motivation
SRS v1.2 (14 Oct 2026) adds an MVP release before R1. Two of its six features are new products of this service:
- **BIL-011** internal biller catalogue and simulated biller settlement, and **BIL-012** mobile recharge via the operator catalogue with MSISDN/prefix validation and simulated fulfilment (UC-16 Bill Payment, UC-17 Mobile Recharge). The MVP also covers **BIL-003** (bill payment by biller and reference), **BIL-005** in part (bill enquiry, simulated only) and **BIL-008** (biller catalogue and biller settlement wallet).
- **A-41**: no external biller or telco call in the MVP, so fulfilment is the in-process simulated provider (`client.SimulatedBillerClient`).
- MVP scope statements for existing products: merchant payment is on-us only (**A-42**); customer cash-out has no OTP or step-up (**A-43**); merchant refund rules are **MER-011** (UC-15); cash-in at agent is **UC-14**.

The producers this depends on are changing in parallel: ledger-service 1.1.0 (commands 18 `post-bill-payment` and 19 `post-recharge`, account type 150 `BILLER_WALLET`, both reversible), wallet-service 1.1.0 (`biller-catalogue-cache` data contract, wallet type `B`), limits-risk-service 1.1.0 and pricing-service 1.1.0 (txnTypes BILL_PAY / RECHARGE).

## 2. Change (before → after)
**Codes (`codes.yaml`)**
- `txnType`: 7 values → + `BILL_PAY` (prefix `BP`, ledger 18), `RECHARGE` (prefix `RC`, ledger 19).
- `txnRefPrefixes`: + `BP`, `RC` (format unchanged, `{prefix}{yyMMdd}00{8 Crockford}`, 18 chars).
- `productCodes`: + `BILL_PAY`, `RECHARGE` (match admin's `FEATURE.BILL_PAY` / `FEATURE.RECHARGE`).
- `failureCode`: + `PROVIDER_REJECTED`.
- `quoteTxnType`: + `BILL_PAY`, `RECHARGE`. New set `rechargeType` {PREPAID, POSTPAID}.
- `problemReasons`: + `NOT_FOUND/BILLER_NOT_FOUND`, `STATE_CONFLICT/BILLER_INACTIVE`, `STATE_CONFLICT/PROVIDER_REJECTED` (with `transaction`), `VALIDATION_FAILED/BILL_REFERENCE_INVALID`, `/BILL_AMOUNT_MISMATCH`, `/BILL_AMOUNT_OUT_OF_RANGE`, `/MSISDN_INVALID`, `/OPERATOR_MISMATCH`. The `transaction` extension also applies to the two new payment operations.
- `metrics`: + `bitspay_transaction_provider_confirm_total`, `bitspay_transaction_compensations_total`, `bitspay_transaction_biller_catalogue_errors_total`.

**REST (`openapi.yaml`, info.version 1.0.0 → 1.1.0)**
- New `POST /v1/bills:enquire` (CUSTOMER; `BillEnquiryRequest {billerId, billReference}` → `BillEnquiryResult {billerId, billerCode, billReference, amountMode, customerName?, dueAmountPoisha?, dueDate?, enquiryRef?, fixedAmountPoisha?, minAmountPoisha, maxAmountPoisha}`).
- New `POST /v1/payments/bill-payment` (CUSTOMER, `Idempotency-Key`; `{customerWalletId, billerId, billReference, amountPoisha, enquiryRef?}` → PaymentResult).
- New `POST /v1/payments/recharge` (CUSTOMER, `Idempotency-Key`; `{customerWalletId, msisdn, operatorBillerId?, rechargeType, amountPoisha}` → PaymentResult).
- `PaymentResult`: + optional `billerId`, `billReference`, `msisdn`, `providerReceipt`, `token` (present on BILL_PAY / RECHARGE only). `TransactionView`: same optional fields.
- `POST /v1/payments/quote`: `txnType` + `BILL_PAY`, `RECHARGE`; new optional request `billerId`; `toWalletId` no longer schema-required (still required for every other txnType; absent for BILL_PAY / RECHARGE) — a relaxation, nobody sending it breaks; `QuoteResult` + optional `billerId`.
- `TxnType`, `FailureCode`, `TxnRef` pattern (`BP`, `RC`) widened; dev `WalletCacheEntry.walletType` + `B`.

```json
// PaymentResult before (P2P unchanged); after, a BILL_PAY adds:
{ "billerId": "0192f9b0-0000-7000-8000-0000000000e1", "billReference": "1234567890", "msisdn": null,
  "providerReceipt": "SIM-BP-BP26101400K7M2QX9D", "token": null }
```

**Events (`txn.events`, all v1 schemas)**: `txnType` + `BILL_PAY`, `RECHARGE`; `fromWalletType` / `toWalletType` + `B`; `failureCode` + `PROVIDER_REJECTED`; `TRANSACTION_COMPLETED`, `TRANSACTION_FAILED`, `TRANSACTION_REVERSED` + optional `billerId`, `billReference`, `msisdn`, `providerReceipt` (not in `required`). The electricity `token` is never published.

**Consumes (`contract.yaml`)**: + `POST /v1/ledger/commands/post-bill-payment` and `post-recharge` (ledger-service 1.1.0, same `fieldsUsed` as the other payment commands); + data `biller-catalogue-cache` v1 (wallet-service 1.1.0, `fieldsUsed` = the keys, `biller:meta.state` and the biller profile fields read); refdata `FEATURE.BILL_PAY`, `FEATURE.RECHARGE`. Existing pins untouched (orchestrator re-pins).

**Behaviour (SPEC)**: pipeline for BILL_PAY / RECHARGE = validate + catalogue → idempotency → wallet status (C → B) → risk → pricing → intent → ledger 18 / 19 → simulated provider confirm (in-process, after ledger OK) → outcome + outbox; provider refusal (references / MSISDNs ending `0000`) → automatic `post-reversal` (reason `SYSTEM_ERROR`) and FAILED `PROVIDER_REJECTED`; no PENDING state. Config `bitspay.billers.mode = SIMULATED` (`EKPAY`, `AGGREGATOR` reserved for R1). BR-TX-93..104, WP-CR-1, F-BP, F-RC, §2 SRS v1.2 trace with MVP markers, §10 scope tags, §13 OPEN TX-MVP-1..8.

## 3. Artefacts touched
<!-- one per line, impact syntax: "METHOD /path[#field]" | <topic>/<EVENT_TYPE>[#field] | codes/<set>[#value] | data/<id> | internal -->
- `POST /v1/bills:enquire`
- `POST /v1/payments/bill-payment`
- `POST /v1/payments/recharge`
- `POST /v1/payments/quote#req.billerId`
- `POST /v1/payments/quote#res.billerId`
- `POST /v1/payments/p2p#res.billerId`
- `POST /v1/payments/p2p#res.billReference`
- `POST /v1/payments/p2p#res.msisdn`
- `POST /v1/payments/p2p#res.providerReceipt`
- `POST /v1/payments/p2p#res.token`
- `GET /v1/transactions/{txnRef}#res.billerId`
- `GET /v1/transactions/{txnRef}#res.billReference`
- `GET /v1/transactions/{txnRef}#res.msisdn`
- `GET /v1/transactions/{txnRef}#res.providerReceipt`
- `GET /v1/transactions/{txnRef}#res.token`
- `GET /v1/transactions#res.items[].billerId`
- `GET /v1/transactions#res.items[].billReference`
- `GET /v1/transactions#res.items[].msisdn`
- `GET /v1/transactions#res.items[].providerReceipt`
- `GET /v1/transactions#res.items[].token`
- `txn.events/TRANSACTION_COMPLETED#billerId`
- `txn.events/TRANSACTION_COMPLETED#billReference`
- `txn.events/TRANSACTION_COMPLETED#msisdn`
- `txn.events/TRANSACTION_COMPLETED#providerReceipt`
- `txn.events/TRANSACTION_FAILED#billerId`
- `txn.events/TRANSACTION_FAILED#billReference`
- `txn.events/TRANSACTION_FAILED#msisdn`
- `txn.events/TRANSACTION_FAILED#providerReceipt`
- `txn.events/TRANSACTION_REVERSED#billerId`
- `txn.events/TRANSACTION_REVERSED#billReference`
- `txn.events/TRANSACTION_REVERSED#msisdn`
- `txn.events/TRANSACTION_REVERSED#providerReceipt`
- `codes/txnType#BILL_PAY`
- `codes/txnType#RECHARGE`
- `codes/failureCode#PROVIDER_REJECTED`
- `codes/quoteTxnType#BILL_PAY`
- `codes/quoteTxnType#RECHARGE`
- `codes/rechargeType`

Notes on the list:
- The optional PaymentResult fields (`billerId`, `billReference`, `msisdn`, `providerReceipt`, `token`) apply to every operation returning PaymentResult and to the problem member `transaction`; they are listed once under p2p to keep the list short.
- Enum widenings in responses and events (`txnType`, `failureCode`, `TxnRef` pattern `BP`/`RC`, `fromWalletType`/`toWalletType` + `B`, quote request `txnType`) are carried by the `codes/...` lines: tolerant readers (kernel K1) are not impacted; consumers that list explicit values in `codesUsed` show up as "review". A dry `impact` run lists the `codesUsed: "*"` readers as review only: `txnType` → pricing, compliance, finance-ops, admin; `failureCode` → treasury, disbursement, admin. They must tolerate the new values (kernel K1); no re-pin is required for kind B.
- `POST /v1/payments/quote#req.toWalletId` is relaxed from schema-required to conditionally required (absent only for BILL_PAY / RECHARGE). A caller that keeps sending it is unaffected, so it is not listed as an impact artefact.
- The new problem reasons (`BILLER_NOT_FOUND`, `BILLER_INACTIVE`, `PROVIDER_REJECTED`, `BILL_REFERENCE_INVALID`, `BILL_AMOUNT_MISMATCH`, `BILL_AMOUNT_OUT_OF_RANGE`, `MSISDN_INVALID`, `OPERATOR_MISMATCH`) are on the new operations and on the quote, so they are additive.
- New consumes (not impact artefacts of this producer): ledger-service `post-bill-payment` / `post-recharge` (1.1.0), wallet-service `data/biller-catalogue-cache` (1.1.0), refdata `FEATURE.BILL_PAY` / `FEATURE.RECHARGE`.

## 4. Proposed versions
| Artefact | From | To |
|---|---|---|
| contractVersion | 1.0.0 | 1.1.0 |
| openapi `info.version` / `x-contract-version` | 1.0.0 | 1.1.0 |
| `txn.events` eventVersion (all four) | 1 | 1 (additive) |
| consumes ledger-service commands 18 / 19 | — | v1 / 1.1.0 |
| consumes wallet-service data `biller-catalogue-cache` | — | v1 / 1.1.0 |

## 5. Adoption Plan
*(generated by `contracts.py cr analyse` on 2026-10-14 — re-run after changing §3)*

### 5.1 Producer — transaction-service (`services/02-transaction-service/`)

- [ ] `contracts/provided/*` — `POST /v1/bills:enquire`; `POST /v1/payments/bill-payment`; `POST /v1/payments/recharge`; `POST /v1/payments/quote#req.billerId`; `POST /v1/payments/quote#res.billerId`; `POST /v1/payments/p2p#res.billerId`; `POST /v1/payments/p2p#res.billReference`; `POST /v1/payments/p2p#res.msisdn`; `POST /v1/payments/p2p#res.providerReceipt`; `POST /v1/payments/p2p#res.token`; `GET /v1/transactions/{txnRef}#res.billerId`; `GET /v1/transactions/{txnRef}#res.billReference`; `GET /v1/transactions/{txnRef}#res.msisdn`; `GET /v1/transactions/{txnRef}#res.providerReceipt`; `GET /v1/transactions/{txnRef}#res.token`; `GET /v1/transactions#res.items[].billerId`; `GET /v1/transactions#res.items[].billReference`; `GET /v1/transactions#res.items[].msisdn`; `GET /v1/transactions#res.items[].providerReceipt`; `GET /v1/transactions#res.items[].token`; `txn.events/TRANSACTION_COMPLETED#billerId`; `txn.events/TRANSACTION_COMPLETED#billReference`; `txn.events/TRANSACTION_COMPLETED#msisdn`; `txn.events/TRANSACTION_COMPLETED#providerReceipt`; `txn.events/TRANSACTION_FAILED#billerId`; `txn.events/TRANSACTION_FAILED#billReference`; `txn.events/TRANSACTION_FAILED#msisdn`; `txn.events/TRANSACTION_FAILED#providerReceipt`; `txn.events/TRANSACTION_REVERSED#billerId`; `txn.events/TRANSACTION_REVERSED#billReference`; `txn.events/TRANSACTION_REVERSED#msisdn`; `txn.events/TRANSACTION_REVERSED#providerReceipt`; `codes/txnType#BILL_PAY`; `codes/txnType#RECHARGE`; `codes/failureCode#PROVIDER_REJECTED`; `codes/quoteTxnType#BILL_PAY`; `codes/quoteTxnType#RECHARGE`; `codes/rechargeType`; `The optional PaymentResult fields (`billerId`, `billReference`, `msisdn`, `providerReceipt`, `token`) apply to every operation returning PaymentResult and to the problem member `transaction`; they are listed once under p2p to keep the list short.`; `Enum widenings in responses and events (`txnType`, `failureCode`, `TxnRef` pattern `BP`/`RC`, `fromWalletType`/`toWalletType` + `B`, quote request `txnType`) are carried by the `codes/...` lines: tolerant readers (kernel K1) are not impacted; consumers that list explicit values in `codesUsed` show up as "review". A dry `impact` run lists the `codesUsed: "*"` readers as review only: `txnType` → pricing, compliance, finance-ops, admin; `failureCode` → treasury, disbursement, admin. They must tolerate the new values (kernel K1); no re-pin is required for kind B.`; `POST /v1/payments/quote#req.toWalletId` is relaxed from schema-required to conditionally required (absent only for BILL_PAY / RECHARGE). A caller that keeps sending it is unaffected, so it is not listed as an impact artefact.`; `The new problem reasons (`BILLER_NOT_FOUND`, `BILLER_INACTIVE`, `PROVIDER_REJECTED`, `BILL_REFERENCE_INVALID`, `BILL_AMOUNT_MISMATCH`, `BILL_AMOUNT_OUT_OF_RANGE`, `MSISDN_INVALID`, `OPERATOR_MISMATCH`) are on the new operations and on the quote, so they are additive.`; `New consumes (not impact artefacts of this producer): ledger-service `post-bill-payment` / `post-recharge` (1.1.0), wallet-service `data/biller-catalogue-cache` (1.1.0), refdata `FEATURE.BILL_PAY` / `FEATURE.RECHARGE`.`
- [ ] `SPEC.md` §5 (tables + examples), §3.1 edge labels, §7 rules, §11 tests as affected
- [ ] `SPEC.md` §10: add **WP-CR-TRANSACTION-1**
- [ ] `contracts/contract.yaml` `contractVersion` bump (MINOR)
- [ ] `SPEC.md` §14 changelog row

### 5.2 Impacted consumers (7)

- [ ] **admin-service** (`services/15-admin-service/`): events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; codes txnType — matched ['P2P', 'CASH_IN', 'CASH_OUT', 'MERCHANT_PAYMENT', 'MERCHANT_REFUND', 'FLOAT_TRANSFER', 'REVERSAL', 'BILL_PAY', 'RECHARGE']; codes txnType — matched ['P2P', 'CASH_IN', 'CASH_OUT', 'MERCHANT_PAYMENT', 'MERCHANT_REFUND', 'FLOAT_TRANSFER', 'REVERSAL', 'BILL_PAY', 'RECHARGE']; codes failureCode — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot admin-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **compliance-service** (`services/11-compliance-service/`): codes txnType — matched *; codes txnType — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot compliance-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **disbursement-service** (`services/08-disbursement-service/`): codes failureCode — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot disbursement-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **finance-ops-service** (`services/12-finance-ops-service/`): events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_COMPLETED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_FAILED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; events txn.events/TRANSACTION_REVERSED — matched *; codes txnType — matched *; codes txnType — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot finance-ops-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **pricing-service** (`services/06-pricing-service/`): codes txnType — matched *; codes txnType — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot pricing-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **support-service** (`services/09-support-service/`): codes txnType — matched ['P2P', 'CASH_IN', 'CASH_OUT', 'MERCHANT_PAYMENT', 'MERCHANT_REFUND', 'FLOAT_TRANSFER', 'REVERSAL', 'BILL_PAY', 'RECHARGE']; codes txnType — matched ['P2P', 'CASH_IN', 'CASH_OUT', 'MERCHANT_PAYMENT', 'MERCHANT_REFUND', 'FLOAT_TRANSFER', 'REVERSAL', 'BILL_PAY', 'RECHARGE']
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot support-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row
- [ ] **treasury-service** (`services/07-treasury-service/`): codes failureCode — matched *
  - update pin in `contracts/contract.yaml`, run `contracts.py snapshot treasury-service`
  - update `SPEC.md` §6 subsection for transaction-service + rules/WPs/tests that use the matched fields; add WP-CR-TRANSACTION-1; changelog row

⚠ Kind B declared but consumers are impacted — reclassify as C.

### 5.3 Not impacted (8) — do not open these packs

- limits-risk-service: events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_FAILED (does not read the changed field); events txn.events/TRANSACTION_FAILED (does not read the changed field); events txn.events/TRANSACTION_FAILED (does not read the changed field); events txn.events/TRANSACTION_FAILED (does not read the changed field); events txn.events/TRANSACTION_REVERSED (does not read the changed field); events txn.events/TRANSACTION_REVERSED (does not read the changed field); events txn.events/TRANSACTION_REVERSED (does not read the changed field); events txn.events/TRANSACTION_REVERSED (does not read the changed field); codes txnType (does not read the changed field); codes txnType (does not read the changed field)
- wallet-service: events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); events txn.events/TRANSACTION_COMPLETED (does not read the changed field); codes txnType (does not read the changed field); codes txnType (does not read the changed field)

## 6. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| Producer owner | Ahmad Naqibul Arefin | Approved | 2026-10-14 |

## 7. Implementation
| Service | WP | MR | Merged |
|---|---|---|---|
| transaction-service | WP-CR-1 | — | — |

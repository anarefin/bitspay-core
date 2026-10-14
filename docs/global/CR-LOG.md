# CR Log

One row per change request across all packs (maintained by `contracts.py cr new|analyse|verify`; state edits by hand allowed for Approved/Closed).

| CR | Producer | Kind | Title | State | Impacted consumers | Created | Updated |
|---|---|---|---|---|---|---|---|
| CR-GENERALLEDGER-1 | general-ledger-service | A | Trace GL spec to SRS v1.1 (module 4.34 GLD) | Closed | — | 2026-10-14 | 2026-10-14 |
| CR-LEDGER-1 | ledger-service | B | MVP: biller account type 150 and bill/recharge commands | Analysed | finance-ops-service, general-ledger-service, transaction-service | 2026-10-14 | 2026-10-14 |
| CR-WALLET-1 | wallet-service | B | MVP: BILLER partner type, wallet type B and biller catalogue | Analysed | disbursement-service, finance-ops-service, general-ledger-service, transaction-service, treasury-service | 2026-10-14 | 2026-10-14 |
| CR-TRANSACTION-1 | transaction-service | B | MVP: BILL_PAY and RECHARGE products with simulated biller | Analysed | admin-service, compliance-service, disbursement-service, finance-ops-service, pricing-service, support-service, treasury-service | 2026-10-14 | 2026-10-14 |
| CR-PRICING-1 | pricing-service | B | MVP: BILL_PAY and RECHARGE fee plans | Analysed | finance-ops-service, transaction-service | 2026-10-14 | 2026-10-14 |
| CR-LIMITSRISK-1 | limits-risk-service | B | MVP: BILL_PAY and RECHARGE limits | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-GENERALLEDGER-2 | general-ledger-service | C | MVP: biller liability mapping; remove GL journal export | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-ADMIN-1 | admin-service | B | MVP: enable BILL_PAY/RECHARGE, MVP feature switches and templates | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-TREASURY-1 | treasury-service | A | MVP scope tagging and SRS v1.2 trace | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-COMPLIANCE-1 | compliance-service | A | MVP scope tagging and SRS v1.2 trace | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-SUPPORT-1 | support-service | A | MVP scope tagging; reversals of BILL_PAY/RECHARGE | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-FINANCEOPS-1 | finance-ops-service | A | MVP scope tagging (out of MVP) and SRS v1.2 trace | Analysed | none | 2026-10-14 | 2026-10-14 |
| CR-DISBURSEMENT-1 | disbursement-service | A | MVP scope tagging (out of MVP) and SRS v1.2 trace | Verified | none | 2026-10-14 | 2026-10-14 |
| CR-TRANSACTION-2 | transaction-service | C | MVP fixed customer PIN | Rejected | disbursement-service | 2026-10-14 | 2026-10-14 |
| CR-WALLET-2 | wallet-service | B | MVP single-step KYC decision | Producer-Applied | none | 2026-10-14 | 2026-10-14 |

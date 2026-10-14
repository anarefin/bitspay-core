# Data contract `gl-export-generic-csv` v1 — daily ERP journal file (format `GENERIC_CSV_V1`)

Owner: general-ledger-service. Version 1 (contractVersion 1.0.0). Served by `GET /v1/gl/exports/{businessDate}/versions/{n}/file` (`text/csv`) and described by `GET /v1/gl/exports/{businessDate}` (`GlExport`). Consumers: the Operator's ERP import (outside the platform) and Finance staff.

## 1. File identity

| Item | Rule |
|---|---|
| File name | `GL_{yyyyMMdd}_v{n}.csv` — `yyyyMMdd` = GL business date, `n` = export version (1, 2, …) |
| Encoding | UTF-8, no BOM, LF line ends, comma separator, RFC 4180 quoting (fields containing `,` `"` or LF are quoted; `"` doubled) |
| Scope | Every journal with status `POSTED` and `businessDate` = the file date (the current `LEDGER_DAY` revision plus every MANUAL, ACCRUAL, ACCRUAL_REVERSAL, REVERSAL, AUTO_INTEREST, YEAR_END_CLOSE, OPENING_BALANCE journal of that date). `SUPERSEDED` ledger revisions are never exported |
| Versioning | A new GL day revision (restatement) of an exported day produces `v{n+1}`; `v{n}` becomes `SUPERSEDED` (still downloadable). Version numbers never repeat |
| Integrity | SHA-256 of the full file bytes is stored and returned as `GlExport.sha256` |

## 2. Header and lines

Header line (exact):

```
journal_date,journal_ref,line_no,gl_account_code,gl_account_name,debit_amount,credit_amount,currency,narration,source_code,transfer_count
```

| Column | Content |
|---|---|
| `journal_date` | journal `businessDate`, `YYYY-MM-DD` |
| `journal_ref` | `GLJ-…` reference (opaque) |
| `line_no` | journal line number, 1-based |
| `gl_account_code` | CoA code (`^[0-9]{4}(-[0-9]{2})?$`) |
| `gl_account_name` | `nameEn` of the account at generation time |
| `debit_amount` | Tk with exactly 2 decimals (`BigDecimal.valueOf(poisha, 2).toPlainString()`), empty when the line is a credit |
| `credit_amount` | same, empty when the line is a debit |
| `currency` | `BDT` |
| `narration` | line narration, else the journal narration (≤ 200 chars) |
| `source_code` | ledger lines: the ledger transfer code (e.g. `2001`); other lines: the journal source (`MANUAL`, `ACCRUAL`, …) |
| `transfer_count` | ledger lines: number of ledger legs aggregated (`legCount`); other lines: empty |

Lines are ordered by `(journal_ref, line_no)`; the `LEDGER_DAY` journal comes first.

## 3. Trailer

Last line (exact key order):

```
#TRAILER,lines=<count>,total_debit=<Tk 2dp>,total_credit=<Tk 2dp>,transfers=<n>,gl_revision=<r>,certification=<PENDING|CERTIFIED|FAILED|NOT_REQUIRED>
```

- `lines` = number of data lines; `total_debit` = `total_credit` (else the build fails, §4).
- `transfers` = Σ `transfer_count` of the **debit** ledger lines (every leg counted once).
- `gl_revision` = GL day revision exported; `certification` = the day's certification at generation time.

## 4. Failure

Σ debit ≠ Σ credit → no file; `GlExport.status = FAILED`, `failureReason = UNBALANCED`, notification `GL_EXPORT_FAILED` (`variant = FAILED`, `errorCode = UNBALANCED`). A technical failure sets `FAILED` with the error code and is retried by `POST /v1/gl/exports/{businessDate}:regenerate` (maker-checker `GlExport`).

## 5. Example (abbreviated)

```
journal_date,journal_ref,line_no,gl_account_code,gl_account_name,debit_amount,credit_amount,currency,narration,source_code,transfer_count
2026-10-09,GLJ-20261009-L-R1,1,1101-01,Trust bank account #01,1000000.00,,BDT,EMONEY_ISSUE EMONEY_ISSUE,1008,1
2026-10-09,GLJ-20261009-L-R1,2,2103,E-money liability - distributors,,1000000.00,BDT,EMONEY_ISSUE EMONEY_ISSUE,1008,1
2026-10-09,GLJ-20261009-L-R1,3,2101,E-money liability - customers,5.00,,BDT,P2P FEE,2001,1
2026-10-09,GLJ-20261009-L-R1,4,4101,Fee income - P2P,,5.00,BDT,P2P FEE,2001,1
#TRAILER,lines=4,total_debit=1000005.00,total_credit=1000005.00,transfers=2,gl_revision=1,certification=CERTIFIED
```

## 6. Extension

Another ERP format is a new implementation of the `ErpFormat` SPI selected by `bitspay.gl.export.format`, with its own data contract file and a new `exportFormat` code. `GENERIC_CSV_V1` stays available.

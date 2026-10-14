# Data contract `refdata-system-params` v1 — reserved `SYSTEM_PARAM` namespaces (owner: admin-service)

Published on `refdata.events` as `REFDATA_UPSERTED` with `type = SYSTEM_PARAM`, key `SYSTEM_PARAM:<code>`, and served by `GET /v1/params/{code}` and `GET /v1/refdata/SYSTEM_PARAM`. The attribute shape of every type is in `refdata-attributes.v1.schema.json`. This file fixes the **reserved namespaces**, the attribute shape of each reserved code and the **seed value** admin-service publishes at start-up. Readers are not listed here: each reader declares the codes it uses in its own `contract.yaml → consumes.refdata`.

## Rules

| # | Rule |
|---|---|
| R1 | Code pattern `^[A-Z][A-Z0-9_]*(\.[A-Z0-9_]+)+$`. The part before the first dot is the namespace. |
| R2 | Reserved namespaces: `FEATURE`, `CUTOFF`, `EOD`, `CALENDAR`, `RETENTION`, `WALLET`, `SUPPORT`, `GL`. No service may invent a code inside a reserved namespace; admin-service adds codes only through its own change process. |
| R3 | Every item carries `attributes.valueType` ∈ `STRING`, `INT`, `BOOL`, `TIME`, `DURATION`, `CRON`, `JSON`, `FEATURE`, `RETENTION`. Scalar types carry `attributes.value`; `FEATURE` and `RETENTION` carry the fields below and no `value`. |
| R4 | `version` +1 per approved change; a republish keeps the version. Readers apply only a higher version (latest wins) and dedupe by `(type, code, version)`. |
| R5 | Never tombstoned. Deactivation = `active: false`. A reader that has received nothing for a code uses its local configuration default. |
| R6 | `FEATURE.<PRODUCT>` and `RETENTION.<CATEGORY>` are written only through `PUT /v1/products/{product}` and `PUT /v1/retention/policies/{category}` / legal holds; the generic param endpoints refuse them (`RESERVED_NAMESPACE`). |

## Reserved codes, attribute shape and seed

| Code / namespace | Attributes | Seed (provisional unless stated) |
|---|---|---|
| `FEATURE.<PRODUCT>` | `{valueType: FEATURE, enabled: bool, channels: array<X-Channel>, licenceRef: string\|null}`. Effective rule (kernel K3.7): allowed ⇔ owner config enabled ∧ (no item received ∨ `enabled`) ∧ (`channels` empty ∨ `X-Channel ∈ channels`). A non-empty `channels` list for `FEATURE.P2P` must contain `SYSTEM` (service-initiated scheduled transfers). | One item per product code found in the generated product-code index. Every seeded item has `channels: []`, `licenceRef: null`. `enabled: true`: `P2P`, `CASH_IN`, `CASH_OUT`, `MERCHANT_PAYMENT`, `MERCHANT_REFUND`, `FLOAT_TRANSFER`, `REVERSAL`. `enabled: false` until licensed (R2): `DISBURSEMENT`, `SCHEDULED_TRANSFER`, `REQUEST_MONEY`, `CAMPAIGN`. `enabled: false` (third-party products not approved, SRS C-01): `ADD_MONEY`, `WALLET_TO_BANK`, `BILL_PAY`, `RECHARGE`, `REMITTANCE`, `CARD`, `OFF_US_QR`. Any other indexed product code: `enabled: false` |
| `CUTOFF.EOD` | `{valueType: TIME, value: "HH:mm"}` — Asia/Dhaka local time at which a new business date starts; `businessDate = localDate(ts @ Asia/Dhaka − value)` | `"00:00"` |
| `CUTOFF.EOD_GRACE_MINUTES` | `{valueType: INT, value: int}` | `15` |
| `CUTOFF.SETTLEMENT_BANK` | `{valueType: TIME, value: "HH:mm"}` | `"15:00"` (no rule uses it yet — OPEN D-49) |
| `EOD.SCHEDULE` | `{valueType: CRON, value: "<6-field Spring cron>"}` | `"0 15 0 * * *"` |
| `CALENDAR.WEEKEND_DAYS` | `{valueType: STRING, value: "FRI,SAT"}` (comma list of `MON..SUN`) | `"FRI,SAT"` |
| `CALENDAR.TIMEZONE` | `{valueType: STRING, value: "Asia/Dhaka"}` | `"Asia/Dhaka"` |
| `RETENTION.<CATEGORY>` | `{valueType: RETENTION, onlineMonths: int32\|null, totalYears: int32, basis: enum{EVENT_DATE, RELATIONSHIP_END, CASE_CLOSURE}, endAction: enum{PURGE, ANONYMISE}, legalHold: bool}`; `legalHold` = an ACTIVE hold with `subjectType = CATEGORY` exists for the category | `FINANCIAL_TXN` 24 / 10 EVENT_DATE PURGE · `CUSTOMER_KYC` null / 5 RELATIONSHIP_END ANONYMISE · `PARTNER` null / 5 RELATIONSHIP_END PURGE · `AML_CASE` 24 / 5 CASE_CLOSURE PURGE (incl. compliance documents) · `AUDIT` 12 / 10 EVENT_DATE PURGE · `NOTIFICATION_LOG` 6 / 5 EVENT_DATE PURGE · `API_LOG` 3 / 1 EVENT_DATE PURGE (incl. system logs) · `RECON` 12 / 10 EVENT_DATE PURGE · `COMPLAINT` 12 / 5 CASE_CLOSURE PURGE · all `legalHold: false` |
| `WALLET.ALLOW_INBOUND_BEFORE_KYC` | `{valueType: BOOL, value: bool}` | `false` |
| `SUPPORT.HELPLINE` | `{valueType: STRING, value: string}` | `"16XXX"` (placeholder, Operator to supply) |
| `GL.FISCAL_YEAR_START_MONTH` | `{valueType: INT, value: 1..12}` — month on whose 1st day the Operator's fiscal year starts | `7` (July, Bangladesh income-tax year; Finance to confirm) |

## Example (`REFDATA_UPSERTED.data`)

```json
{ "type": "SYSTEM_PARAM", "code": "RETENTION.AUDIT", "parentCode": null, "nameEn": "Retention: audit", "nameBn": "সংরক্ষণ: অডিট",
  "attributes": { "valueType": "RETENTION", "onlineMonths": 12, "totalYears": 10, "basis": "EVENT_DATE", "endAction": "PURGE", "legalHold": false },
  "version": 1, "active": true }
```

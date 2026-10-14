# Data contract `biller-catalogue-cache` v1 — Redis format of the biller catalogue

Owner: wallet-service, partner module (writer). Kind: redis-format. contractVersion 1.1.0 (introduced by CR-WALLET-1, MVP). Readers pin this file (`consumes.data`); a change that is not additive is a new version (`biller-catalogue-cache.v2.md`) served alongside v1.

The catalogue is the set of activated partners of type `BILLER` (SRS v1.2 BIL-008, BIL-011, BIL-012). Each biller settles into its own wallet of type `B` (ledger account type 150 `BILLER_WALLET`, owner type 6 `BILLER`). Readers use this cache to validate a bill payment or a mobile recharge and to find the biller wallet to credit, without calling wallet-service on the hot path.

## 1. Location

- Redis **cache** cluster (`BITSPAY_REDIS_CACHE_URL`), the same cluster as `wallet-status-cache`; no TTL on `biller:*`.
- Every key is a plain string key; no operation of this contract touches more than one key, so it is Redis-Cluster safe without hash tags.

## 2. Keys and values

| Key | Type | Value | Present when |
|---|---|---|---|
| `biller:{billerId}` | string | UTF-8 JSON object of §3 | the biller has been activated (it has a `walletId`); kept for every later status (SUSPENDED, PENDING_TERMINATION, TERMINATED) |
| `biller:mno-prefix:{prefix}` | string | `billerId` (canonical lower-case UUID, 36 chars) | an MNO biller that is not TERMINATED lists `prefix` in `msisdnPrefixes` |
| `biller:meta` | hash | `state` (EMPTY / LOADING / READY), `loadedAt` (ISO-8601 UTC), `schema` = `1`, `count` (billers written by the last refresh) | after the first refresh; diagnostics only |

- `{billerId}` = the partnerId of the biller, canonical lower-case UUID, e.g. `biller:0192f4a0-0b01-7c00-8a00-00000000b001`.
- `{prefix}` = the 3-digit local mobile prefix `01[3-9]` (e.g. `017`), i.e. `"0" +` characters 4..5 of the canonical MSISDN `8801XXXXXXXXX` (`8801712345678` → `017`).

## 3. `biller:{billerId}` JSON (schema 1)

| Field | Type | Null | Meaning |
|---|---|---|---|
| `schema` | int | N | always `1` in this version |
| `billerId` | uuid | N | = partnerId (= key suffix) |
| `version` | int64 | N | partner row version = `PARTNER_UPSERTED.version`; strictly increasing per biller; the CAS compares it |
| `billerCode` | string | N | short unique code `^[A-Z0-9-]{2,16}$`, e.g. `DESCO`, `GP`; immutable after activation |
| `partnerCode` | string | N | `^B[0-9]{9}$` |
| `subType` | enum | N | `UTILITY`, `EDUCATION`, `GOVT_FEE`, `INTERNET_TV`, `MNO` (codes.yaml `partnerSubType`, partnerType BILLER) |
| `category` | enum | N | codes.yaml `billerCategory`: `UTILITY_ELECTRICITY`, `UTILITY_GAS`, `UTILITY_WATER`, `INTERNET`, `TV`, `EDUCATION`, `GOVT_FEE`, `MOBILE_PREPAID`, `MOBILE_POSTPAID` |
| `categoryCode` | int32 | N | codes.yaml `categoryCode` 501..505 (same as the biller wallet's) |
| `nameEn` | string | N | 1..100 chars |
| `nameBn` | string | N | 1..100 chars |
| `logoKey` | string | Y | object-store key of the logo (channels resolve it); null = no logo |
| `status` | enum | N | partner status (codes.yaml `partnerStatus`); **only `ACTIVE` is payable** |
| `walletId` | uuid | N | the biller's settlement wallet (type `B`); the credit account of ledger commands 18 / 19 |
| `referenceLabelEn` | string | N | e.g. `Account number` |
| `referenceLabelBn` | string | N | e.g. `হিসাব নম্বর` |
| `referencePattern` | string | N | Java-compatible regular expression (≤ 200 chars) that the **whole** bill reference must match; MNO billers use `^01[3-9][0-9]{8}$` (the local MSISDN) |
| `amountMode` | enum | N | codes.yaml `billerAmountMode`: `ENQUIRY`, `FIXED`, `OPEN` |
| `fixedAmountPoisha` | int64 | Y | set iff `amountMode = FIXED`; within min..max |
| `minAmountPoisha` | int64 | N | ≥ 1 |
| `maxAmountPoisha` | int64 | N | ≥ `minAmountPoisha` |
| `feeBearer` | enum | N | codes.yaml `billerFeeBearer`: `PAYER`, `BILLER` |
| `msisdnPrefixes` | array<string> | N | MNO only (`^01[3-9]$`, 1..10 items, unique across live MNO billers); `[]` otherwise |
| `rechargeTypes` | array<enum> | N | MNO only, subset of `PREPAID`, `POSTPAID` (≥ 1 item); `[]` otherwise |
| `denominationsPoisha` | array<int64> | N | MNO only, optional quick picks, each within min..max, ascending; `[]` when none or not MNO |
| `updatedAt` | timestamp | N | ISO-8601 UTC with milliseconds; last change of the partner or its profile |

Readers ignore unknown fields (kernel K1); a value that does not parse as JSON or has `schema ≠ 1` is treated as a miss. Example (DESCO, activated, version 3):

```json
{"schema":1,"billerId":"0192f4a0-0b01-7c00-8a00-00000000b001","version":3,"billerCode":"DESCO","partnerCode":"B000000018","subType":"UTILITY","category":"UTILITY_ELECTRICITY","categoryCode":501,"nameEn":"Dhaka Electric Supply Company (DESCO)","nameBn":"ঢাকা ইলেকট্রিক সাপ্লাই কোম্পানি (ডেসকো)","logoKey":"billers/desco.png","status":"ACTIVE","walletId":"0192f4a1-0b01-7c00-8a00-00000000b001","referenceLabelEn":"Account number","referenceLabelBn":"হিসাব নম্বর","referencePattern":"^[0-9]{8,12}$","amountMode":"ENQUIRY","fixedAmountPoisha":null,"minAmountPoisha":1000,"maxAmountPoisha":5000000,"feeBearer":"PAYER","msisdnPrefixes":[],"rechargeTypes":[],"denominationsPoisha":[],"updatedAt":"2026-10-14T06:00:00.000Z"}
```

Example (Grameenphone, MNO) and its prefix keys `biller:mno-prefix:017` → `0192f4a0-0b07-7c00-8a00-00000000b007`, `biller:mno-prefix:013` → the same id:

```json
{"schema":1,"billerId":"0192f4a0-0b07-7c00-8a00-00000000b007","version":3,"billerCode":"GP","partnerCode":"B000000075","subType":"MNO","category":"MOBILE_PREPAID","categoryCode":505,"nameEn":"Grameenphone","nameBn":"গ্রামীণফোন","logoKey":"billers/gp.png","status":"ACTIVE","walletId":"0192f4a1-0b07-7c00-8a00-00000000b007","referenceLabelEn":"Mobile number","referenceLabelBn":"মোবাইল নম্বর","referencePattern":"^01[3-9][0-9]{8}$","amountMode":"OPEN","fixedAmountPoisha":null,"minAmountPoisha":1000,"maxAmountPoisha":100000,"feeBearer":"PAYER","msisdnPrefixes":["017","013"],"rechargeTypes":["PREPAID","POSTPAID"],"denominationsPoisha":[2000,5000,10000,20000,50000],"updatedAt":"2026-10-14T06:00:00.000Z"}
```

## 4. Write rule (writer: wallet-service partner module only)

The biller key is written through this Lua compare-and-set (loaded with `SCRIPT LOAD`, called with `EVALSHA`, fallback `EVAL` on `NOSCRIPT`):

```lua
-- KEYS[1] = biller:{billerId}; ARGV[1] = version; ARGV[2] = JSON value (§3)
local cur = redis.call('GET', KEYS[1])
if cur then
  local ok, obj = pcall(cjson.decode, cur)
  if ok and type(obj) == 'table' and tonumber(obj['version']) and tonumber(obj['version']) >= tonumber(ARGV[1]) then
    return 0
  end
end
redis.call('SET', KEYS[1], ARGV[2])
return 1
```

- Returns `1` = applied, `0` = stale or duplicate. A biller key is never deleted.
- Only when the CAS returns `1` does the writer maintain the prefix index: `SET biller:mno-prefix:{p} {billerId}` for every prefix in the new value (none when `status = TERMINATED`), then, for every prefix the biller held in the previous value but not in the new one, a compare-and-delete (`if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0`) so another operator's key is never removed.
- Sources of writes: (a) write-through after the database commit of every change of an activated biller (activation FINALISE, approved profile change, status change, category change, termination); (b) the refresh job `biller-cache-refresh` (cache-loader role, every 60 s and at start-up): it reads every BILLER partner with a `walletId` from the database and applies the CAS for each (newer wins), rebuilds the prefix keys, then sets `biller:meta`. The cache is fully rebuildable from the database.
- PENDING_SCREENING, PENDING_APPROVAL and REJECTED billers (no wallet) are never written.

## 5. Read rule (readers)

1. **By id:** `GET biller:{billerId}`. Payable only when `status = ACTIVE`.
2. **By MSISDN (recharge):** derive the prefix (§2), `GET biller:mno-prefix:{prefix}` → `billerId`, then step 1. Accept the result only if `subType = MNO` and `prefix ∈ msisdnPrefixes`; otherwise treat it as a miss (the index may briefly lag the biller key). If the caller also named an operator, it must equal the resolved `billerId`.
3. **Validation inputs:** the bill reference must fully match `referencePattern`; the amount must be within `minAmountPoisha..maxAmountPoisha`, and equal `fixedAmountPoisha` when `amountMode = FIXED`; the credit account is `walletId`.
4. **Miss:** call `GET /v1/billers/{billerId}` (or `GET /v1/billers?msisdnPrefix={prefix}` for step 2) on wallet-service (provided API) with single-flight and a circuit breaker; the response carries the fields of §3 except `schema`. A `404` means unknown or not activated.
5. If both Redis and the fallback are unavailable, the reader refuses safely (`503 DEPENDENCY_UNAVAILABLE`); it never guesses a biller, a status or a wallet.
6. Unknown `status`, `category`, `amountMode`, `subType` or `feeBearer` values are handled safely (treated as not payable) — open enums, kernel K1.

## 6. Test vectors

| Input | Expected |
|---|---|
| MSISDN `8801712345678` | prefix `017`, key `biller:mno-prefix:017` |
| MSISDN `8801312345678` | prefix `013` |
| MSISDN `8801512345678` | prefix `015` (TELETALK in the seed catalogue) |
| CAS stored version 3, write version 3 | `0` (duplicate) |
| CAS stored version 3, write version 4 | `1` |
| Stored value `not-json` | treated as a miss by readers; writer CAS overwrites it (`1`) |
| DESCO, reference `12345678`, `^[0-9]{8,12}$` | matches |
| DESCO, reference `1234567` | does not match (`BILL_REFERENCE_INVALID` at the reader) |

## 7. Changelog

| Version | Date | Change |
|---|---|---|
| 1 (contract 1.1.0) | 2026-10-14 | Introduced by CR-WALLET-1 (MVP biller catalogue) |

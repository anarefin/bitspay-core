# Data contract `transfer-id-derivation` v1 (owner: ledger-service)

Kind: algorithm + golden vectors. Golden vectors: `transfer-id-golden-vectors.v1.json` (same folder). Any change to the algorithm is **breaking** (v2).

## 1. Algorithm

```
transferId(commandId, legIndex) = first 16 bytes of SHA-256( uuidBytes(commandId) || uint8(legIndex) )
  — interpreted as an unsigned 128-bit big-endian integer;
  — if the result is 0 or 2^128 - 1, set legIndex += 128 and recompute (the retried index is used only for hashing;
    TB user_data_32 keeps the original leg index).
```

- `uuidBytes(commandId)` = the 16 bytes of the UUID in RFC 4122 network (big-endian) order.
- `uint8(legIndex)` = one byte, 0..255.
- **Text form:** canonical lower-case UUID text (8-4-4-4-12) of the big-endian 128-bit value. Never 32-hex, never prefixed.
- Every TigerBeetle transfer created by ledger-service has `id = transferId(commandId, legIndex)`; the ledger never generates a random transfer id.
- `commandId` is the command's `commandId`; for a disbursement row it is the **row** `commandId`.

## 2. Leg index conventions (fixed by position)

| Command | Leg indexes |
|---|---|
| 1–6, 18, 19 payments | 0 principal · 1 fee · 2 VAT · 3 commission · 4 AIT · 5–8 technical balance-bounds legs (only when `destinationMaxBalancePoisha` is set). A skipped leg (amount 0) keeps its index; later legs never shift |
| 7 reversal | 0 void of `releaseHoldCommandId`'s hold (only if present) · `1 + i` = mirror of original leg `i` (i = 0..4). All legs 0–5 are business legs |
| 8 disbursement row | 0 principal · 5–8 technical when the row has constraints |
| 9, 10, 11, 16 | 0 |
| 12 campaign reward | 0 · 5–8 technical when constraints are set |
| 13 commission settlement | 0 net commission · 1 AIT (only if `aitPoisha > 0`) |
| 14 create-hold | 0 (pending) |
| 15 release-hold | 0 (void) |
| 17 closure payout | 0 · 5–8 technical when constraints are set |
| account close | 0 of `closeCommandId = UUIDv5(LEDGER_NS, "close:" + accountId)`, `LEDGER_NS = 6f1c0e1a-0b1d-4c9e-9d0a-6c2b7e3f8a01` (technical code 9005) |

Technical transfers are identified **by code** (9001–9099), never by leg index.

## 3. UUID ↔ TigerBeetle u128 (Java client)

`hi = uuid.getMostSignificantBits()`, `lo = uuid.getLeastSignificantBits()`; pass `UInt128.asBytes(lo, hi)` to the Java client (TB byte arrays are little-endian — never pass the UUID bytes directly). Round trip: `00000000-0000-0000-0000-000000000200` ↔ u128 `0x200`. Leg-0 golden vector as u128 halves: hi `0xfc214b7cf80c8143`, lo `0x4f0e107e2518a302`.

## 4. Who may use it

Any service may recompute a transfer id to match `transferIds`, `ledger.changes` `transferId` (= `eventId`) or read-API rows. Only ledger-service creates transfers.

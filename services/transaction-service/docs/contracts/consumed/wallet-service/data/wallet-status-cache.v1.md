# Data contract `wallet-status-cache` v1 — Redis format of the wallet status cache

Owner: wallet-service (writer). Kind: redis-format. contractVersion 1.0.0. Readers pin this file (`consumes.data`); a change that is not additive is a new version (`wallet-status-cache.v2.md`) served alongside v1.

## 1. Location

- Redis **cache** cluster (`BITSPAY_REDIS_CACHE_URL`), no TTL on `ws:*`.
- One hash per bucket; 131,072 buckets (fixed by this contract, not configurable).

## 2. Key, field, value

```
uuidBytes(id) = 16 bytes big-endian of the canonical UUID (most significant 8 bytes ‖ least significant 8 bytes)
h      = MurmurHash3_x86_32(uuidBytes, seed = 0)         // Java: commons-codec MurmurHash3.hash32x86(bytes, 0, 16, 0)
bucket = unsigned(h) mod 131072                          // == h & 0x1FFFF ; never Math.abs(h)
key    = "ws:" + bucket                                  // decimal, e.g. "ws:86318"
field  = base64url without padding of uuidBytes          // 22 chars, e.g. "AZLyqhw-e1GKLV4PPJt6AQ"
value  = version ":" statusCode ":" kycTier ":" walletTypeCode ":" categoryCode ":" flags
```

| Value part | Type | Meaning |
|---|---|---|
| `version` | decimal int64, 1 ≤ v < 2^53 | wallet row version = `WALLET_UPSERTED.version`; strictly increasing per wallet |
| `statusCode` | one of `P A D X C F Q Z` | effective wallet status (codes.yaml `walletStatus`, incl. debit / credit permissions) |
| `kycTier` | `0` `1` `2` | KYC tier |
| `walletTypeCode` | one of `C A D M I` | codes.yaml `walletType` |
| `categoryCode` | decimal int32 0..99999 | codes.yaml `categoryCode` (never an MCC) |
| `flags` | decimal int32 0..31 | codes.yaml `walletFlag` bitmask |

Readers parse the value by splitting on `:` into exactly 6 parts; any other shape is treated as a miss.

## 3. Write rule (writers: wallet-service only)

Every write goes through this Lua compare-and-set (loaded with `SCRIPT LOAD`, called with `EVALSHA`, fallback `EVAL` on `NOSCRIPT`):

```lua
-- KEYS[1] = ws:{bucket}; ARGV[1] = field; ARGV[2] = version; ARGV[3] = value
local cur = redis.call('HGET', KEYS[1], ARGV[1])
if cur then
  local v = tonumber(string.match(cur, '^(%d+):'))
  if v and v >= tonumber(ARGV[2]) then return 0 end
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
return 1
```

- Returns `1` = applied, `0` = stale or duplicate. A field is never deleted; a closed wallet stays with status `Z`.
- Sources of writes: write-through after the database commit of every wallet change, read-repair after a status read, and the cache loader that follows the compacted `wallet.events` topic (group `wallet-service.status-cache-loader`). The cache is fully rebuildable from that topic.
- `wsmeta:loader` (hash) carries `state` (EMPTY / LOADING / READY), `loadedAt`, `schema = 1`; readers may use `state` for diagnostics only.

## 4. Read rule (readers)

1. Fetch the sender and receiver fields in one round trip (pipelined `HGET`).
2. On a miss call `GET /v1/wallets/{walletId}/status` (wallet-service provided API) with single-flight and a circuit breaker. Its response carries the same six values.
3. On a `404` from that call the reader may write the negative-cache key `wsn:{walletId}` (canonical lower-case uuid) with value `1` and TTL 60 s, and treats the wallet as unknown while the key exists. Only readers write `wsn:*`; wallet-service `DEL`s `wsn:{walletId}` when the wallet becomes READY (before its first CAS).
4. If both Redis and the fallback are unavailable, the reader refuses safely (`503 DEPENDENCY_UNAVAILABLE`); it never guesses a status.
5. Unknown `statusCode` / `walletTypeCode` values are handled safely (treated as not transactable) — open enums, kernel K1.

## 5. Test vectors (MurmurHash3_x86_32, seed 0)

| walletId | murmur3 (hex, unsigned) | bucket | key | field |
|---|---|---|---|---|
| `0192f2aa-1c3e-7b51-8a2d-5e0f3c9b7a01` | `3e71512e` | 86318 | `ws:86318` | `AZLyqhw-e1GKLV4PPJt6AQ` |
| `0192f2bb-4d5f-7c62-9b3e-6f1a4dac8b12` | `d4e79e6e` (signed −723018130) | 106094 | `ws:106094` | `AZLyu01ffGKbPm8aTayLEg` |
| `01929a3c-0000-7000-8000-000000000001` | `d0e6c737` | 50999 | `ws:50999` | `AZKaPAAAcACAAAAAAAAAAQ` |
| `00000000-0000-0000-0000-000000000200` (a ledger system account, never a wallet) | `514cd28e` | 53902 | `ws:53902` | `AAAAAAAAAAAAAAAAAAACAA` |

Example values: `8813:A:2:C:0:0` (customer, tier 2, active), `8813:F:1:C:0:0` (customer frozen), `9002:A:2:M:3101:0` (MICRO grocery merchant).

## 6. Changelog

| Version | Date | Change |
|---|---|---|
| 1 | 2026-10-13 | v6 baseline |

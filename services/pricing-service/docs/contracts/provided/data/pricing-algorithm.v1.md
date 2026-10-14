# Data contract `pricing-algorithm` v1 — fee, VAT and commission evaluation

| Item | Value |
|---|---|
| Owner | pricing-service (module `pricing`) |
| Contract id / version | `pricing-algorithm` / 1 (`contracts/contract.yaml → provides.data`) |
| Kind | shared algorithm (normative) |
| Companion | `pricing-golden-vectors.v1.json` (machine-readable test vectors, same version) |
| Rounding | `HALF_EVEN` (banker's rounding), integer arithmetic only |

Every service that computes a fee from a plan published on `fee.rules` implements this algorithm **identically**. pricing-service runs it behind `POST /v1/pricing/quote`; any other implementation must produce the same nine output values for every input. Conformance is proven by passing every `tier: "CATALOGUE"` vector of `pricing-golden-vectors.v1.json`. The `tier: "EXTENSION"` vectors are informative for other implementations and mandatory for pricing-service.

The algorithm is a pure function. It performs no I/O, reads no clock (the caller supplies `at`) and never throws for a plan that conforms to the `PlanJson` schema (`events/fee.rules/PRICING_PLAN_UPSERTED.v1.schema.json`). It must also produce the documented result for plans that bypassed plan validation (vectors X6, X7).

## 1. Inputs

| Name | Type | Notes |
|---|---|---|
| `plans` | list of `PlanJson` | the evaluator's current snapshot: one value per `planId` (the latest `fee.rules` value; tombstoned plans removed) |
| `txnType` | enum `P2P`, `CASH_IN`, `CASH_OUT`, `MERCHANT_PAYMENT`, `MERCHANT_REFUND`, `FLOAT_TRANSFER`, `REVERSAL` | |
| `channel` | enum `X-Channel` values, or null | null matches only plans whose `match.channel` is null |
| `amountPoisha` | int64, 1..10^13 | principal |
| `payer`, `payee` | `{walletType enum{C,A,D,M,I}, kycTier int32 0..9, categoryCode int32 ≥ 0}` | `categoryCode` 0 for customers; partner codes per the wallet-service category vocabulary (AGENT 101–104, DISTRIBUTOR 201–203, MERCHANT `3000 + size×100 + MCC group`, INSTITUTION 401–404) |
| `usage.senderMonthlyCountForTxnType` | int32 ≥ 0 | sender's count for this `txnType` in the current month **before** this transaction; absent → 0 |
| `at` | timestamp | evaluation instant; absent → caller's current time |

## 2. Output (exactly nine fields)

| Field | Type | Null | Rule |
|---|---|---|---|
| `planId` | string | Y | selected plan; null = no plan matched |
| `planVersion` | int32 | Y | null iff `planId` null |
| `feePoisha` | int64 | N | ≥ 0 |
| `vatPoisha` | int64 | N | ≥ 0 |
| `feeBearer` | enum `PAYER`, `PAYEE`, `OPERATOR` | Y | echoed from the plan; null iff no plan. `SHARED` is reserved and never produced (OPEN D-03) |
| `commissionPoisha` | int64 | N | gross commission after the commission clamp |
| `aitPoisha` | int64 | N | 0 ≤ ait ≤ commissionPoisha |
| `commissionSource` | enum `FEE_INCOME`, `COMMISSION_PAYABLE` | Y | echoed from the plan (may be non-null while commission is 0) |
| `commissionBeneficiary` | enum `PAYER`, `PAYEE` | Y | echoed from the plan |

A consumer that needs a non-null bearer maps `feeBearer: null` to `PAYER` itself; the algorithm never does.

Reserved and never emitted in v1: `vatOnCommissionPoisha` (OPEN D-02).

## 3. Rounding primitive

```
bpsOf(base: int64 ≥ 0, bps: int32 0..10000) -> int64
    n = base × bps                       // exact; ≤ 10^13 × 10^4 = 10^17 < 2^63, use multiplyExact
    q = n div 10000 ; r = n mod 10000
    if r > 5000 or (r == 5000 and q is odd): q = q + 1
    return q
```

`bpsOf(base, bps)` equals `BigDecimal(base) × bps / 10000` rounded `HALF_EVEN` to scale 0. Floating-point types (`double`, `float`) are forbidden anywhere in the computation.

Checks: `bpsOf(1000, 125) = 12` (12.5 → 12), `bpsOf(1000, 175) = 18` (17.5 → 18), `bpsOf(750, 1500) = 112` (112.5 → 112), `bpsOf(35000, 150) = 525`, `bpsOf(525, 1500) = 79` (78.75 → 79), `bpsOf(75, 1000) = 8` (7.5 → 8), `bpsOf(45, 1000) = 4` (4.5 → 4).

## 4. Algorithm (normative pseudo-code)

```
evaluate(plans, in) -> Result

  // step 0 — resolved category
  if in.payee.walletType in {A, D, M, I}:  cat = in.payee.categoryCode
  else:                                    cat = in.payer.categoryCode
  // CASH_OUT, MERCHANT_PAYMENT, FLOAT_TRANSFER → payee; CASH_IN, MERCHANT_REFUND → payer; P2P → 0

  at    = in.at ?? now()
  usage = in.usage?.senderMonthlyCountForTxnType ?? 0

  // step 1 — candidates
  candidates = [ p in plans where
        p.status == ACTIVE
    and p.txnType == in.txnType
    and p.effectiveFrom <= at
    and (p.effectiveTo == null or at < p.effectiveTo)          // effectiveTo is exclusive
    and (p.match.channel         == null or p.match.channel         == in.channel)
    and (p.match.payerWalletType == null or p.match.payerWalletType == in.payer.walletType)
    and (p.match.payeeWalletType == null or p.match.payeeWalletType == in.payee.walletType)
    and (p.match.payerKycTier    == null or p.match.payerKycTier    == in.payer.kycTier)
    and (p.match.categoryCode    == null or p.match.categoryCode    == cat) ]

  // step 2 — selection
  if candidates is empty:
      return { planId: null, planVersion: null, feePoisha: 0, vatPoisha: 0, feeBearer: null,
               commissionPoisha: 0, aitPoisha: 0, commissionSource: null, commissionBeneficiary: null }
  p = first of candidates ordered by
        priority DESC,
        count of non-null match fields DESC,
        version DESC,
        planId ASC (lexicographic, code-point order)

  // step 3 — free allowance
  freeApplied = p.freeMonthlyCount > 0 and usage < p.freeMonthlyCount

  // step 4 — fee
  if freeApplied:
      fee = 0                                                   // no clamp
  else:
      switch p.fee.type:
        FIXED:   fee = p.fee.fixedPoisha
        PERCENT: fee = bpsOf(in.amountPoisha, p.fee.percentBps)
        SLAB:    s   = the slab with s.fromPoisha <= amount and (s.toPoisha == null or amount <= s.toPoisha)
                 fee = s.fixedPoisha + bpsOf(in.amountPoisha, s.percentBps)
        NONE:    fee = 0
      if p.fee.type != NONE:                                    // NONE is never clamped (vector X6)
          fee = max(fee, p.fee.minPoisha)
          if p.fee.maxPoisha > 0: fee = min(fee, p.fee.maxPoisha)

  // step 5 — VAT on the fee
  vat = bpsOf(fee, p.vatBps)

  // step 6 — commission (gross), clamp, AIT
  switch p.commission.type:
    NONE:              gross = 0
    FIXED:             gross = p.commission.fixedPoisha
    PERCENT_OF_AMOUNT: gross = bpsOf(in.amountPoisha, p.commission.valueBps)
    PERCENT_OF_FEE:    gross = bpsOf(fee, p.commission.valueBps)          // fee from step 4 (0 when free)
  if p.commission.type != NONE:                                           // OPEN D-27 (vectors X8, X9)
      cMin = p.commission.minPoisha ?? 0 ; cMax = p.commission.maxPoisha ?? 0
      gross = max(gross, cMin)
      if cMax > 0: gross = min(gross, cMax)
  ait = bpsOf(gross, p.commission.aitBps)

  // step 7 — operator-borne fee
  if p.feeBearer == OPERATOR:                                   // mandatory in every evaluator (vector X7)
      fee = 0 ; vat = 0                                         // count a consistency metric if it was > 0

  // step 8 — output
  return { planId: p.planId, planVersion: p.version, feePoisha: fee, vatPoisha: vat,
           feeBearer: p.feeBearer, commissionPoisha: gross, aitPoisha: ait,
           commissionSource: p.commission.source, commissionBeneficiary: p.commission.beneficiary }
```

## 5. Rules that are easy to get wrong

| # | Rule | Vector |
|---|---|---|
| 1 | `effectiveTo` is **exclusive**; `effectiveFrom` inclusive | X3 |
| 2 | A null `match` field matches anything; `match.channel = null` matches every channel, but a request with `channel = null` matches only plans with `match.channel = null` | — |
| 3 | `categoryCode` is compared with the **resolved** category of step 0, never with the payer's value blindly | X2 |
| 4 | Tie-break order is priority → specificity → version → planId | G11, G12 |
| 5 | The free allowance zeroes the fee **without** applying `minPoisha`; VAT and `PERCENT_OF_FEE` commission are then 0, amount-based commission is still computed | G7, X5 |
| 6 | `fee.type = NONE` is never clamped, even when a plan carries `minPoisha > 0` | X6 |
| 7 | Slab boundaries are inclusive on both ends; amount 100000 uses the first slab of the reference plan | G5 |
| 8 | `maxPoisha = 0` (fee or commission) means "no cap" | G6, X8 |
| 9 | The commission clamp applies **before** AIT and only for `commission.type ≠ NONE`; absent `commission.minPoisha` / `commission.maxPoisha` = 0 | X8, X9 |
| 10 | Whether `commission.minPoisha` applies when the unclamped gross is 0 because the fee was zeroed by the free allowance is **undecided** (OPEN D-27). Until decided, plan validation rejects plans that combine `commission.minPoisha > 0`, `PERCENT_OF_FEE` and `freeMonthlyCount > 0`, so the case never reaches an evaluator | — |
| 11 | `feeBearer = OPERATOR` forces `fee = vat = 0` in the output even when the computed fee was > 0 | X7 |
| 12 | `commissionSource` / `commissionBeneficiary` are echoed even when `commissionPoisha = 0` | X5 |
| 13 | The result must be independent of the order of `plans` | property test |

## 6. Vector file format (`pricing-golden-vectors.v1.json`)

| Field | Type | Notes |
|---|---|---|
| `schemaVersion` | int32 | `1` |
| `catalogueVersion` | string | `"1.4"` (the contract generation the values were fixed in) |
| `rounding` | string | `"HALF_EVEN"` |
| `outputFields` | array<string> | the nine §2 names; a runner compares **all** of them |
| `vectors` | array<Vector> | `tier: "CATALOGUE"`: G1–G12, X1, X2, X6, X7, X8, X9 — mandatory for every implementation |
| `extensionVectors` | array<Vector> | `tier: "EXTENSION"`: X3, X4, X5 — mandatory for pricing-service, informative for others |
| `Vector.id` | string | |
| `Vector.tier` | enum `CATALOGUE`, `EXTENSION` | |
| `Vector.provisional` | bool | always `false` |
| `Vector.description` | string | |
| `Vector.plans` | array<PlanJson> or string `"SAME_AS:<id>"` | `SAME_AS` reuses the plan list of another vector |
| `Vector.input` | quote request (§1) | `at` = `2026-10-09T08:00:00.000Z` in every vector |
| `Vector.expected` | result (§2) | |

Runner: for each vector, load `plans` into a fresh evaluator, evaluate `input`, compare every `outputFields` value. Every plan object in the file is a complete `PlanJson` (timestamps with three millisecond digits, `commission.minPoisha` / `maxPoisha` present). Plans in X6 and X7 deliberately violate plan validation; an evaluator must load them without validating.

Change rules: changing or removing a `CATALOGUE` vector, or changing any rule in §3–§4, is a **breaking** change (`pricing-algorithm` v2 with dual publication). Adding a vector that the current algorithm already satisfies is additive. The file is also served at `GET /v1/pricing/golden-vectors` with `ETag` = lower-case hex SHA-256 of the response body; other implementations copy it byte-for-byte into their test resources.

## 7. Summary of the vectors

| # | Plan (summary) | amount | usage | → fee | vat | commission | ait |
|---|---|---|---|---|---|---|---|
| G1 | P2P FIXED 500, vat 1500 | 50000 | 0 | 500 | 75 | 0 | 0 |
| G2 | CASH_OUT PERCENT 150, vat 1500, comm PERCENT_OF_FEE 4000, ait 1000 | 50000 | 0 | 750 | 112 | 300 | 30 |
| G3 | CASH_IN NONE, comm PERCENT_OF_AMOUNT 40 (COMMISSION_PAYABLE), ait 1000 | 100000 | 0 | 0 | 0 | 400 | 40 |
| G4 | MERCHANT_PAYMENT PERCENT 150, bearer PAYEE | 35000 | 0 | 525 | 79 | 0 | 0 |
| G5 | P2P SLAB (1..100000 fixed 500; ≥ 100001 50 bps), max 2500 | 100001 | 0 | 500 | 75 | 0 | 0 |
| G6 | as G5 | 1000000 | 0 | 2500 | 375 | 0 | 0 |
| G7 | P2P FIXED 500, freeMonthlyCount 5 | 50000 | 4 | 0 | 0 | 0 | 0 |
| G8 | as G7 | 50000 | 5 | 500 | 75 | 0 | 0 |
| G9 | P2P PERCENT 125 | 1000 | 0 | 12 | 2 | 0 | 0 |
| G10 | P2P PERCENT 175 | 1000 | 0 | 18 | 3 | 0 | 0 |
| G11 | priority 100 (FIXED 500) vs 200 (FIXED 300) | 50000 | 0 | 300 | 45 | 0 | 0 |
| G12 | same priority; `payerKycTier = 2` plan (FIXED 400) beats generic (FIXED 500) | 50000 | 0 | 400 | 60 | 0 | 0 |
| X1 | FLOAT_TRANSFER, no plan | 5000000 | 0 | 0 | 0 | 0 | 0 (all nullable outputs null) |
| X2 | MERCHANT_PAYMENT, plan `categoryCode 3101` PERCENT 100 vs generic PERCENT 150 | 35000 | 0 | 350 | 52 | 0 | 0 |
| X6 | CASH_IN fee NONE with `minPoisha 1000` | 100000 | 0 | 0 | 0 | 0 | 0 |
| X7 | P2P FIXED 500, bearer OPERATOR | 50000 | 0 | 0 | 0 | 0 | 0 |
| X8 | CASH_IN, comm PERCENT_OF_AMOUNT 40, `commission.maxPoisha 2000` | 1000000 | 0 | 0 | 0 | 2000 | 200 |
| X9 | as X8 with `commission.minPoisha 500`, max 0 | 50000 | 0 | 0 | 0 | 500 | 50 |
| X3 | promo (prio 200) ends exactly at `at`; standard FIXED 500 wins | 50000 | 0 | 500 | 75 | 0 | 0 |
| X4 | PERCENT 50, `minPoisha 1000` | 10000 | 0 | 1000 | 150 | 0 | 0 |
| X5 | CASH_OUT FIXED 1000, free 3, comm PERCENT_OF_FEE 4000 | 50000 | 1 | 0 | 0 | 0 | 0 |

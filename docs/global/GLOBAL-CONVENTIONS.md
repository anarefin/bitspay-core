# Bits Pay — Global Conventions (the Kernel)

**Kernel version: 1.0** (2026-10-13). Derived from: Contract Catalogue v1.4 sections §0, §1.1–§1.3, the generic part of §1.4, §1.5 (rule only), §7.1, the generic parts of §8.1–§8.3, §12 and §13.3–13.4; Engineering Standards v5.0 §1–§16; GL addendum (CCR-GL-01, applied).

> **What the kernel is.** These are the only rules that every service shares. They are generic: no service's payload, enum or code list appears here. Everything service-specific belongs to the service that owns it, in `services/<NN>-<service>/contracts/`.
>
> **The kernel changes rarely.** A change is a **kind-E change request** (see `CHANGE-PROCESS.md`), approved by the architect. Every pack records the kernel version it was written against (`contract.yaml` → `kernel`).
>
> **Precedence:**
> 1. The kernel wins over a service spec on every topic it covers.
> 2. A service spec wins for anything the kernel leaves to the owner.
> 3. A producer's `contracts/provided/*` wins over any prose describing it, including the producer's own SPEC.md tables. If the two disagree, that is a bug in the SPEC.md table.

---

## K1. Data conventions

| Item | Rule |
|---|---|
| Money | `int64` in **poisha** (1 Tk = 100 poisha). Field names end in `Poisha`. No decimals, no floats, anywhere money is computed or carried. Exceptions are declared by the owning producer in its own contract, e.g. ledger balance members `debitsPosted`. |
| Currency | `"BDT"` only in this phase. TigerBeetle `ledger = 1` = BDT (`2` reserved for USD). |
| Entity IDs | **UUIDv7** strings, lower-case, hyphenated (8-4-4-4-12). Every 128-bit ledger ID in JSON (account, transfer, pending, command) is rendered as canonical lower-case UUID text of the big-endian u128: never 32-hex, never prefixed. STAFF identifiers (`X-Actor-Id`, `makerId`, `checkerId`, `staffUserId`) are canonical UUIDs too. |
| Time | ISO-8601 UTC with `Z` and millisecond precision (`2026-10-09T08:03:22.123Z`). Producers always emit the 3 ms digits; consumers accept both `…:22Z` and `…:22.123Z`. The single exception is TigerBeetle `timestamp` (JSON number, u64 ns since epoch), and only where the ledger's contract says so. |
| Business date | `businessDate` = `YYYY-MM-DD` in Asia/Dhaka: `businessDate = localDate(ts @ Asia/Dhaka − CUTOFF.EOD)`. `CUTOFF.EOD` is a `SYSTEM_PARAM` published by admin-service (`refdata.events`). Default `00:00` until it is received. Every service that emits a `businessDate` consumes it and pins it in its `contract.yaml`. |
| References | Every `txnRef`-like reference is an **opaque string** of 1..32 characters `[A-Z0-9-]` for every consumer. Its internal format belongs to its owner. Consumers never parse it. |
| Type names in field tables | `string`, `uuid`, `int32`, `int64`, `int64 (poisha)`, `bool`, `timestamp` (ISO-8601 UTC ms Z), `date` (`YYYY-MM-DD` Asia/Dhaka), `enum{…}`, `object`, `array<T>`. Column `Req` = key always present. Column `Null` = value may be JSON `null`. |
| Unknown fields | **Tolerant reader everywhere.** Every reader ignores unknown fields in responses, event `data` and the envelope. Requests reject unknown fields only where the provider's contract says so. |
| Open enums | A consumer that switches on a producer enum must handle an unknown value safely (ignore, count, or route to a default). A new enum value is an **additive** change for the producer. |

## K2. Canonical hashing of personal identifiers

This is the one rule for every service that hashes an identifier (wallet, partner, limits-risk, compliance, campaign). Equal inputs must give equal hashes everywhere.

```
hash = lowercase_hex( HMAC-SHA256( key = BITSPAY_PLATFORM_HMAC_KEY,
                                   message = UTF-8(normalize(type, value)) ) )      // 64 hex chars
```

| type | `normalize` |
|---|---|
| `NID` | digits only; valid lengths 10, 13 or 17 |
| `MSISDN` | digits only; `01XXXXXXXXX` → `8801XXXXXXXXX`; result must be 13 digits |
| `PASSPORT` / other ID documents | letters and digits only, upper-case |
| `DEVICE` | trimmed, as given |
| `WALLET`, `PARTNER` | lower-case canonical UUID |
| `BANK_ACCOUNT` | `<bankCode>:<account digits>` |
| `IP` | canonical textual form (IPv4 dotted quad; IPv6 RFC 5952) |

- **Key.** The key is the same secret in every service: env var `BITSPAY_PLATFORM_HMAC_KEY` (property `bitspay.crypto.platform-hmac-key`).
- **JSON value.** The bare 64-char hex string `^[0-9a-f]{64}$`, with no prefix. Use `null` when the identifier is unknown.
- **Clear values never travel in a URL for `NID` or `BANK_ACCOUNT`.** Callers send a `valueHash`.
- **Display masks:**
  - MSISDN: `8801711****00`
  - NID: `******` + last 4
  - others: first 4 + `****`
- **Who masks.** The **presenting** service applies masks (UI, notification template, report). Producers of events and notification requests send full values, never pre-masked ones. The only exception is a display name the producer holds only in masked form; those fields are named `…Masked`.

## K3. HTTP contract

### K3.1 Request headers (all services)

The edge layer (gateway + auth) is out of scope in this phase. Callers pass the actor context in trusted headers. A later gateway will set the same headers after validating a JWT, so no service changes will be needed.

| Header | Type | Req | Constraints | Meaning |
|---|---|---|---|---|
| `X-Correlation-Id` | string | yes (generate if absent) | ≤ 64, `[A-Za-z0-9._-]` | Propagated to all downstream calls, logs, `envelope.correlationId` and the problem body |
| `X-Actor-Type` | enum | yes | `CUSTOMER` \| `AGENT` \| `MERCHANT` \| `DISTRIBUTOR` \| `INSTITUTION` \| `STAFF` \| `SYSTEM` \| `SERVICE` | `SERVICE` = a synchronous call by another service on its own authority. `SYSTEM` = a scheduled job, internal automation, or a platform tool (E2E, perf, IVR/chatbot adaptor) |
| `X-Actor-Id` | string | yes | ≤ 64. Canonical UUID for `CUSTOMER` (customerId); for `AGENT`/`MERCHANT`/`DISTRIBUTOR`/`INSTITUTION` (partnerId); for `STAFF` (staffUserId). For `SERVICE`/`SYSTEM`: the bare `spring.application.name` matching `^[a-z][a-z-]*-service$`, or the tool name | Actor identity |
| `X-Actor-Wallet-Id` | uuid | for wallet holders | canonical UUID | Wallet the actor is operating |
| `X-Actor-Roles` | string | for STAFF | comma-separated K7 role codes, no spaces | Staff roles |
| `X-Actor-User-Id` | string | optional | ≤ 64, `[A-Za-z0-9_-]` | Individual user inside a partner actor. Used only for maker ≠ checker and for audit, never for authorisation |
| `X-Channel` | enum | yes | `APP` \| `USSD` \| `PARTNER_APP` \| `PORTAL` \| `BACKOFFICE` \| `API` \| `SYSTEM` (closed) | Channel of origin |
| `X-Device-Id` | string | optional | ≤ 128 | Device (fraud rules). Not forwarded on SERVICE calls; contracts that need the device carry it in the body (`deviceId`) |
| `Idempotency-Key` | string | on every money-moving POST, and on every POST whose provider contract says so | ≤ 64, `[A-Za-z0-9_-]` | Client-generated, unique per actor. Scope `(X-Actor-Id, key)`. Rules in K3.3 |
| `traceparent` | string | optional | W3C Trace Context | Tracing |

Header validation:
- A missing or ill-formed required header → `400 VALIDATION_FAILED`, with `errors[].field` = the header name.
- An actor type, role or caller that is not permitted → `403 ACTOR_NOT_ALLOWED`.

### K3.2 Outbound service calls

A service calling another service sends the following, unless the **provider's** contract states that the caller forwards an actor context:

| Header | Value |
|---|---|
| `X-Actor-Type` | `SERVICE` for a synchronous call; `SYSTEM` for scheduled jobs, automation and platform tools |
| `X-Actor-Id` | the caller's bare `spring.application.name` |
| `X-Channel` | the channel of the inbound request that caused the call; `SYSTEM` when there is none (jobs, sweepers, event consumers, bootstrap) |
| `X-Correlation-Id` | propagated from the inbound request or event |
| `Idempotency-Key` | as the provider's contract requires |

- End-user context (initiator, channel, device) travels in request **bodies**, not in forwarded actor headers.
- **Forwarding.** A forwarded actor context (the caller passes the end actor's `X-Actor-*` headers through unchanged) is allowed only where the provider's contract lists that caller and operation.
- **Merged services.** A merged service always sends its bare service name, never `<service>/<module>`. A provider that restricts a caller to one module of a merged service checks `X-Actor-Id = <service>`. The caller guarantees internally that only that module makes the call: the call lives only in that module's outbound adapter, which is checked by review.

### K3.3 Idempotency-Key rules

| # | Rule |
|---|---|
| 1 | **Provider retention ≥ 7 days.** Store `(X-Actor-Id, key) → request hash + response` for at least 7 days. *(OPEN D-01 — 7 days is the decided value; kept as a tag for traceability.)* |
| 2 | Same key + same payload within retention → **replay** the original response: the outcome of *that* request, not the current state. Same key + different payload → `409 IDEMPOTENCY_CONFLICT`. |
| 3 | **Callers never reuse a key more than 72 h** after its first use. |
| 4 | Before retrying an attempt whose first try is **older than 24 h**, the caller resolves the outcome with the provider's lookup operation (named in the provider's contract). It retries only if no outcome exists. |
| 5 | **A definitive refusal is final for its key.** A 400, 403, 404, 409 or 422 closes the attempt; a new attempt needs a **new key**. The same key is reused **only** after a `503`, a timeout, a connection error or another 5xx. |
| 6 | A provider may define a different idempotency mechanism (e.g. the ledger's `commandId`) or declare an operation read-only and key-free. That exception is part of the provider's contract. |

### K3.4 Pagination

The scheme is cursor-based: `?limit=50&cursor=<opaque>` → `{ "items": [...], "nextCursor": "..." | null }`.

| Param / field | In | Type | Req | Null | Constraints |
|---|---|---|---|---|---|
| `limit` | query | int32 | no | — | 1..200, default 50. A value outside 1..200 → `400 VALIDATION_FAILED` (`errors[].field = "limit"`). A provider may declare a different default in its contract |
| `cursor` | query | string | no | — | Opaque. Valid for 24 h, and only for the same endpoint, actor and filter set. Expired, tampered or foreign → `400 VALIDATION_FAILED`, `reason = INVALID_CURSOR` |
| `items` | body | array<T> | yes | no | 0..`limit` items. T and the ordering are defined by the provider |
| `nextCursor` | body | string | yes | yes | `null` on the last page |

A list that is not paged must say so, and state its bound, in the provider's contract.

Schema: `schemas/page.schema.json`.

### K3.5 Standard money object

```json
{ "amountPoisha": 50000, "feePoisha": 500, "vatPoisha": 75, "totalDebitPoisha": 50575, "feeBearer": "PAYER", "currency": "BDT" }
```

| Field | Type | Req | Null | Constraints |
|---|---|---|---|---|
| `amountPoisha` | int64 (poisha) | yes | no | > 0, ≤ 10^13 |
| `feePoisha` | int64 (poisha) | yes | no | ≥ 0 (0 when no plan / waived) |
| `vatPoisha` | int64 (poisha) | yes | no | ≥ 0 (VAT on the fee) |
| `totalDebitPoisha` | int64 (poisha) | yes | no | = `amountPoisha` + (`feeBearer = PAYER` ? `feePoisha + vatPoisha` : 0) |
| `feeBearer` | enum | yes | no | `PAYER` \| `PAYEE` \| `OPERATOR`. `SHARED` is reserved and not accepted *(OPEN D-03)* |
| `currency` | string | yes | no | `"BDT"` |

Providers extend this object in their own contracts. Schema: `schemas/money.schema.json`.

### K3.6 Errors — RFC 9457 problem+json

`Content-Type: application/problem+json`. Clients switch on `code` (a closed kernel list) and on `reason` (owned by each provider).

**Closed `code` list** (kernel-owned; a provider never returns another `code`):

| HTTP | `code` | Generic meaning |
|---|---|---|
| 400 | `VALIDATION_FAILED` | Bad input: schema, format, range, header or cursor. Always 400, never 422 |
| 403 | `ACTOR_NOT_ALLOWED` | Actor type, role or caller not permitted. 403 only; 401 is reserved for the future edge layer |
| 404 | `NOT_FOUND` | Entity missing |
| 409 | `IDEMPOTENCY_CONFLICT` | Same idempotency key, different payload |
| 409 | `STATE_CONFLICT` | Invalid state transition |
| 409 | `SOD_VIOLATION` | Segregation-of-duties refusal |
| 422 | `INSUFFICIENT_FUNDS` | Ledger rejected (exceeds credits) |
| 422 | `LIMIT_EXCEEDED` | Limits engine rejected |
| 422 | `RISK_BLOCKED` | Fraud engine BLOCK |
| 422 | `RISK_STEP_UP_REQUIRED` | Fraud engine STEP_UP (handled by the future auth layer) |
| 422 | `RISK_HELD_FOR_REVIEW` | Fraud engine HOLD |
| 422 | `WALLET_NOT_TRANSACTABLE` | Wallet status blocks this direction |
| 422 | `MAX_BALANCE_EXCEEDED` | Receiver would exceed its max balance |
| 422 | `REFUND_EXCEEDS_ORIGINAL` | Refund amount > refundable remainder |
| 422 | `SERVICE_DISABLED` | Product or channel disabled (K3.7) |
| 422 | `MAKER_CHECKER_VIOLATION` | Checker = maker, or a required approval is missing |
| 503 | `DEPENDENCY_UNAVAILABLE` | Safe refusal: "try again". Never move money on an unknown state |

**Generic problem body** (kernel-owned; schema `schemas/problem.schema.json`, `additionalProperties: true`):

| Field | Type | Req | Null | Notes |
|---|---|---|---|---|
| `type` | string | yes | no | URI; default `about:blank` |
| `title` | string | yes | no | ≤ 200 |
| `status` | int32 | yes | no | = HTTP status |
| `code` | enum | yes | no | Closed list above |
| `detail` | string | no | yes | ≤ 1000, free text, **no PII**. Never parsed by clients; never carries a machine reason |
| `instance` | string | no | yes | Request path |
| `correlationId` | string | yes | no | = `X-Correlation-Id` |
| `reason` | string | no | yes | `^[A-Z][A-Z0-9_]*$`. **Values are owned by the provider**: declared per operation in its OpenAPI and listed in its `codes.yaml → problemReasons` |
| `errors` | array<{field, message}> | with `VALIDATION_FAILED` | no | ≥ 1 item. `field` = JSON path, query param or header name |
| `retryable` | bool | with 503 | no | Always `true` |
| *extension members* | any | per provider | — | **Owned by the provider of the operation.** Declared in its OpenAPI response schema and in `codes.yaml → problemExtensions` (e.g. transaction-service's `transaction`, limits fields on `LIMIT_EXCEEDED`, wallet's `walletStatus`) |

Kernel-reserved `reason` values (usable by any provider): `INVALID_CURSOR`.

**Rules:**
- A new `reason` value or a new extension member is an **additive** change for its provider.
- A consumer that branches on a `reason` or extension lists it in its `fieldsUsed`/`codesUsed`.

### K3.7 Product switches (rule only)

A service that owns a product honours **both**:
- its static config `bitspay.features.<product>.enabled`, and
- the governance switch `SYSTEM_PARAM FEATURE.<PRODUCT>` on `refdata.events` (published by admin-service).

**Effective rule:** product allowed ⇔ config enabled **and** (no `FEATURE.<PRODUCT>` item received yet **or** its `enabled = true`) **and** (`channels` empty **or** `X-Channel ∈ channels`). If the product is not allowed → `422 SERVICE_DISABLED`, before any side effect.

**Who owns what:**
- **Product codes:** declared by the owning service in `codes.yaml → productCodes`.
- **Attribute schema:** owned by admin-service, in its `refdata.events` contract.
- **Consumption:** each owner consumes `refdata.events` for its own `FEATURE.*` codes, version-guarded (latest `version` wins; dedupe on `(type, code, version)`).

## K4. Events

### K4.1 Envelope (all topics)

Schema `schemas/envelope.schema.json` (`additionalProperties: true`).

```json
{ "eventId": "0192f3c1-7a2b-7c00-9a51-3f2c8e1d0b99", "eventType": "TRANSACTION_COMPLETED", "eventVersion": 1,
  "occurredAt": "2026-10-09T08:03:22.123Z", "producer": "transaction-service", "aggregateType": "Transaction",
  "aggregateId": "0192f2aa-0001-7000-8000-00000000a001", "correlationId": "c-0f3e9a", "data": { } }
```

| Field | Type | Req | Null | Constraints |
|---|---|---|---|---|
| `eventId` | uuid | Y | N | lower-case canonical. UUIDv7 and **= outbox row `id`** for outbox events. A producer may define another derivation in its contract (ledger: `= transferId`). Consumers dedupe on `eventId` |
| `eventType` | string | Y | N | `^[A-Z][A-Z0-9_]*$`; one of the types the producer declares for the topic |
| `eventVersion` | int32 | Y | N | ≥ 1; per eventType, as declared by the producer (schema file `<EVENT_TYPE>.v<n>.schema.json`) |
| `occurredAt` | timestamp | Y | N | ISO-8601 UTC ms Z |
| `producer` | string | Y | N | bare service name `^[a-z][a-z-]*-service$` (or `archiver`). Never `<service>/<module>` |
| `aggregateType` | string | Y | N | domain entity type, fixed per eventType by the producer |
| `aggregateId` | string | Y | N | minLength 1; **= Kafka record key** |
| `correlationId` | string | Y | N | 1..64; the triggering request's `X-Correlation-Id` (jobs generate one) |
| `data` | object | Y | N | per the producer's schema `contracts/provided/events/<topic>/<EVENT_TYPE>.v<n>.schema.json` |

### K4.2 Producing — transactional outbox

- Publish only through the service's single outbox table `svc_<name>.outbox`, written in the **same DB transaction** as the state change (K8.2 DDL).
- **Routing:**
  - outbox `aggregate_type` = topic name
  - `aggregate_id` = Kafka key = envelope `aggregateId`
  - `id` = envelope `eventId`
- Debezium Outbox Event Router options:
  - `route.by.field=aggregate_type`
  - `route.topic.replacement=${routedByValue}`
  - `table.field.event.key=aggregate_id`
  - `table.field.event.payload=payload`
  - `route.tombstone.on.empty.payload=true`
- Fallback `bitspay.outbox.relay=polling` behaves identically.
- A producer may declare a non-outbox transport in its contract (only `ledger.changes`, via `ledger-cdc-bridge`).
- **Tombstones:**
  - A tombstone is a Kafka record with the topic's key and a **null value** (no envelope).
  - It is allowed **only** on compacted topics whose producer contract declares `tombstones: true` (today only `fee.rules`) *(OPEN D-31)*.
  - Written as an outbox row with `payload = NULL`.
  - On every other topic, a null payload is a producer bug.

### K4.3 Consuming — inbox, retries, DLQ

- **Idempotency:** process the event and insert `processed_event(event_id)` in **one DB transaction**; on conflict, skip. A different intrinsic idempotent effect is allowed if the consumer's spec states it.
- **Retries:** 5 attempts with exponential backoff, then `<topic>.dlq`.
- **Non-retryable failures** (deserialisation, malformed JSON, envelope schema violation) go to `<topic>.dlq` immediately.
- **DLQ records:**
  - keep the original key and value
  - carry headers `x-error` (≤ 1 KB, no PII), `x-error-class`, `x-original-topic`, `x-original-partition`, `x-original-offset`, `x-original-timestamp`, `x-consumer-group`, `x-retries`
- **Records to ignore and count** with `bitspay_consumer_events_ignored_total{topic,group,event_type,reason}`, where `reason ∈ {UNKNOWN_TYPE, FILTERED, NULL_VALUE}`:
  - an unknown `eventType`
  - a filtered event
  - a null value on a topic without tombstones
- **Delivery:** at least once. Never assume exactly-once or cross-topic ordering.
- **Versioning:** additive fields only within one `eventVersion`. Consumers ignore unknown fields.
- **Consumer group id:** matches `^<service-name>(\.[a-z0-9-]+)?$`. The consumer chooses it and declares it in its own `contract.yaml`. A merged service's second module uses the purpose prefix `<module>-` (e.g. `wallet-service.partner-refdata-events`). One exception is allowed: per-instance groups `<service>.<purpose>-${HOSTNAME}`, which must be declared as such.

### K4.4 Inbound topics (consumer-owned schemas)

Three topics are written **by many services into one owner**. The **receiving** service owns their schema, and every writer pins it like a consumed contract (`consumes.inboundTopics`):

| Topic | Schema owner | Writers |
|---|---|---|
| `notification.requests` | admin-service (notification module) | any service that sends notifications |
| `approval.events` | admin-service (governance module) | every service with maker-checker |
| `audit.events` | admin-service (governance module) | every service |

Template codes and variables sent on `notification.requests` are declared by each **sender** in its own `codes.yaml → notificationTemplates`. admin-service seeds text for them from those declarations.

## K5. Maker-checker pattern

Each service that owns sensitive config or actions implements maker-checker **locally**, with no runtime dependency on admin-service.

- **Table:** `approval_request(id, entity_type, entity_id, action, payload jsonb, maker_id, status, level, required_levels, amount_poisha, created_at, expires_at, decided_by[], decided_at)`.
- **Endpoints (same in every such service):**
  - `POST /v1/approvals/{id}:approve` `{comment?}`
  - `POST /v1/approvals/{id}:reject` `{comment (1..500), reasonCode? ^[A-Z_]{3,40}$}`
  - `GET /v1/approvals?status=PENDING&entityType=&cursor=&limit=`
- **Errors:**
  - `403 ACTOR_NOT_ALLOWED`: role not in the current level's `checkerRoles`
  - `404 NOT_FOUND`
  - `409 STATE_CONFLICT`: not PENDING, expired, or revalidation failed
  - `422 MAKER_CHECKER_VIOLATION`
- **Rules:**
  - The checker must differ from the maker. When both carry `X-Actor-User-Id`, those values are compared too.
  - A level-2+ checker must differ from every earlier-level checker.
  - The number of levels is set by amount thresholds (config).
  - Requests expire after 72 h by default.
- **Partner-actor checkers** are identified by `X-Actor-Id` = the owning partner and a present `X-Actor-User-Id` that differs from the maker's. `checkerRoles[]` lists **staff roles only**.
- **Events:** publishes `approval.events` and `audit.events` (schemas owned by admin-service, K4.4). A merged service sets `data.module`.
- **`entityType` values:** a closed vocabulary **owned by the service**, listed in its `codes.yaml → entityTypes`. Adding a value is additive. Governance routes by `(service, module, entityType)` → `(service, module, *)` → `(service, *, *)` → `ADMIN`, so a new value never breaks routing.

## K6. Audit

- **Every** state-changing API writes an `audit.events` outbox row in the same DB transaction. Exceptions are declared in the producer's spec, e.g. per-payment outcomes of transaction-service, whose trail is `txn.events` chained by governance.
- **Never put any of these in `before`/`after`:**
  - PIN, OTP, passwords, tokens, keys
  - clear NID, document bytes, bank account numbers (use `nidMasked` and the last 4 digits of an account)
  - unmasked MSISDN (mask as `8801711****00`) or unmasked e-mail (keep the first character + domain)
  - a case narrative
- Truncate free text (`note`, `comment`) to 140 characters.

## K7. Staff role codes (provisional; enforced via `X-Actor-Roles` until auth exists)

`OPS_MAKER`, `OPS_CHECKER`, `FIN_MAKER`, `FIN_CHECKER`, `SUP_AGENT`, `SUP_MAKER`, `SUP_CHECKER`, `RISK_ANALYST`, `RISK_CHECKER`, `COMPLIANCE_OFFICER`, `CAMLCO`, `PARTNER_OPS_MAKER`, `PARTNER_OPS_CHECKER`, `PRICING_MAKER`, `PRICING_CHECKER`, `ADMIN`, `AUDITOR`, `READ_ONLY`. (general-ledger-service uses `FIN_MAKER` / `FIN_CHECKER` / `AUDITOR` — no new role, CCR-GL-01.)

These are the only values allowed in:
- `approval.events.checkerRoles[]`
- `audit.events.actorRoles[]`
- `notification.requests.recipient.role`

Staff groups map to roles as follows. Send one notification request per role.

| Group | Roles |
|---|---|
| Finance | `FIN_MAKER` / `FIN_CHECKER` |
| Ops | `PARTNER_OPS_MAKER` / `OPS_CHECKER` |
| Compliance | `COMPLIANCE_OFFICER` / `CAMLCO` |

## K8. Platform

### K8.1 Service identity, ports and naming

- `spring.application.name` is the bare service name. It is also:
  - the outbound `X-Actor-Id`
  - the envelope `producer`
  - the metric label `service`
- Ports:
  - local HTTP port: `81NN`, where NN = the service number
  - management port: `91NN` (`/actuator/*`)
- The service table is in `SYSTEM-CONTEXT.md`.
- Edge proxy (dev/local only, nginx on 8000): routes `/<svc-short>/` with `X-Forwarded-Prefix` and never authenticates.

### K8.2 Database layout and outbox

- One PostgreSQL 18 database `bitspay`. Each service owns **exactly one schema** `svc_<name>`, used only by the login role of the same name.
- No cross-schema access, joins, foreign keys, views or grants. No physical sharding.
- Exactly one outbox per service: `svc_<name>.outbox`. Moving it, or adding a schema, is a kind-E change.

```sql
CREATE TABLE IF NOT EXISTS outbox (
  id             uuid PRIMARY KEY,                    -- = envelope eventId
  aggregate_type text        NOT NULL,                -- = Kafka topic
  aggregate_id   text        NOT NULL,                -- = Kafka key = envelope aggregateId
  event_type     text        NOT NULL,
  payload        jsonb       NULL,                    -- full envelope; NULL = tombstone (only where declared)
  created_at     timestamptz NOT NULL DEFAULT now(),
  published_at   timestamptz                          -- polling relay only
);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS processed_event (
  event_id     uuid PRIMARY KEY,
  topic        text NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT now()
);
```

- Cleanup jobs delete outbox rows older than 3 days and `processed_event` rows older than 14 days.
- Locally, one Debezium connector `outbox-all` (slot `dbz_outbox`, `table.include.list = svc_[a-z_]+\.outbox`) reads every outbox.

### K8.3 Runtime configuration contract

Every service image runs unmodified in the Compose stack and honours these settings:

| Env var | Property | Example |
|---|---|---|
| `SPRING_PROFILES_ACTIVE` | profiles | `dev` |
| `SERVER_PORT` / `MANAGEMENT_SERVER_PORT` | ports | `8103` / `9103` |
| `SPRING_DATASOURCE_URL`, `_USERNAME`, `_PASSWORD` | datasource | `jdbc:postgresql://postgres:5432/bitspay?currentSchema=svc_wallet`, user `svc_wallet` |
| `SPRING_KAFKA_BOOTSTRAPSERVERS` | Kafka | `kafka-1:9092` |
| `BITSPAY_REDIS_CRITICAL_URL` / `BITSPAY_REDIS_CACHE_URL` | Redis | `redis://redis-critical:6379` |
| `BITSPAY_CLIENTS_<SVC>_BASEURL` | `bitspay.clients.<svc>.base-url` | `http://ledger-service:8101` (keys per service in `SYSTEM-CONTEXT.md`) |
| `BITSPAY_OUTBOX_RELAY` | `bitspay.outbox.relay` | `debezium` \| `polling` |
| `BITSPAY_SECURITY_MODE` | `bitspay.security.mode` | `trusted-headers` |
| `BITSPAY_PLATFORM_HMAC_KEY` | `bitspay.crypto.platform-hmac-key` | K2 |
| `BITSPAY_FIELD_CIPHER_KEY` | `bitspay.crypto.field-cipher-key` | per service |
| `OTEL_SDK_DISABLED` | OpenTelemetry | `true` in this phase |
| `JAVA_TOOL_OPTIONS` | JVM | `-XX:MaxRAMPercentage=75 -XX:+UseZGC -XX:+ExitOnOutOfMemoryError` |
| `SERVER_FORWARDHEADERSSTRATEGY` | `server.forward-headers-strategy` | `framework` |

Service-specific variables (TigerBeetle, ClickHouse, S3) are declared in that service's SPEC §3.3.

### K8.4 Metrics contract (generic part)

- **HTTP:** `http_server_requests_seconds`, with percentile histograms and common tag `service`. Merged services add the tag `module`.
- **Outbox:** `bitspay_outbox_unpublished_rows` (gauge, `service`).
- **Consumers:**
  - `bitspay_consumer_event_age_seconds{topic,group}`
  - `bitspay_consumer_dlq_published_total{topic}`
  - `bitspay_consumer_events_ignored_total{topic,group,event_type,reason}`
- **Service-specific metrics:** follow `bitspay_<service>_<thing>_<unit|total>` and are declared in the owner's SPEC §9. Their names are part of the owner's contract (`codes.yaml → metrics`).

## K9. Engineering standards

| Area | Rule |
|---|---|
| Stack | Java 25 (virtual threads), Spring Boot 4.1.x, Gradle 9.8.1 Kotlin DSL, PostgreSQL 18 + Flyway + Spring Data JPA (Hibernate; Flyway owns the schema, `ddl-auto: validate`), Redis 8.10 (clusters **critical**: idempotency and counters; **cache**: wallet status and display data), Kafka 4.3 (KRaft) + Debezium 3.7, Caffeine, Resilience4j, springdoc-openapi, Micrometer, JUnit 5 / AssertJ / Testcontainers 2.x / WireMock / ArchUnit (layering and money rules) / Awaitility / jqwik. TigerBeetle 0.17.9 is used only by ledger-service; ClickHouse 26.8 only by finance-ops reporting. |
| Build | Each service is a **standalone single-project Gradle build** in `services/<svc>/`, with its own wrapper, `settings.gradle.kts`, version catalog and lock file. No `include`, `includeBuild`, `../` paths or `mavenLocal()`. The standard block is copied from `platform/build-template/`. |
| Layout | Traditional layered Spring Boot, under package root `com.bracits.bitspay.<service>`: `controller` (REST, returns DTOs) / `dto` (request/response records) / `service` (business logic, transactions, jobs, policies) / `repository` (Spring Data JPA) / `entity` (JPA entities, enums, value objects) / `mapper` (entity ↔ DTO) / `exception` (exceptions + problem+json advice) / `client` (concrete outbound clients: `Http<Svc>Client`, object store, TigerBeetle) / `messaging` (Kafka consumers, outbox writer, inbox) / `config` (Spring config, `ActorContext` filter, `@RequiresActor`). Dependencies run controller → service → repository / client / messaging; no ports or adapters, no interfaces with one implementation. `ArchitectureTest` (ArchUnit) enforces that controllers are called by nobody and never use entities, only services use repositories and clients, and nothing skips the service layer. |
| No shared runtime code | Envelope, `ActorContext`, error model, outbox/inbox, idempotency, maker-checker and crypto helpers are implemented **inside each service**. Copying is allowed; linking is not. |
| Contract-first, never wait | Implement provided contracts exactly as in `contracts/provided/`. Every consumed API is stubbed with WireMock from `contracts/consumed/` (pre-built in `stubs/`). Every consumed event has a fixture (`fixtures/events/`). Each downstream service is called through one concrete `client.Http<Svc>Client` (base URL `bitspay.clients.<svc>.base-url`); tests and profile `local` point it at WireMock. The only in-process fake is transaction-service's `FakeLedgerClient`, because its provided contract exposes it (`/v1/internal/dev/fake-ledger/*`); it is a profile-guarded second implementation of `client.LedgerClient`. A full stack is never needed to build or test one service. |
| Profiles | `local` (own infra in Docker plus WireMock on 8099), `dev` (full Compose stack), `hybrid` (this service in the IDE, the rest in Compose). |
| API style | REST/JSON, plural nouns, actions as `POST /resource/{id}:action`. Jakarta Validation. Read actor context only through `ActorContext` (filled from `X-Actor-*`); authorisation via `@RequiresActor(types, roles)`. Timeouts on every outbound call (default 300 ms connect / 1 s read, unless the consumer's spec sets one) and a circuit breaker on every dependency. |
| Money and correctness | (1) Money is `long` poisha. (2) Rounding is `HALF_EVEN`, and only in pricing calculations. (3) No balance changes outside ledger-service; corrections are compensating ledger commands. (4) Write the intent, move the money, record the outcome, and write the outbox row in the outcome's transaction. (5) If a money decision depends on a value you cannot read, refuse with 503; never guess. (6) Every financial command has a stable `commandId`. (7) jqwik property tests for any amount computation or split. |
| Data and security | One schema `svc_<name>`; nothing cross-schema. NID is stored encrypted (AES-GCM via a `FieldCipher` component), with `nid_hash` (K2). Mask MSISDN and NID in logs. No secrets in Git. `timestamptz` UTC. Mutable rows have `created_at`, `updated_at` and `version`. |
| Observability | JSON logs with fields `ts, level, service, correlationId, traceId, actorId, txnRef?, msg`, and no PII. RED metrics per endpoint. Liveness and readiness at `/actuator/health/{liveness,readiness}`. |
| Testing | `service` package line coverage ≥ 90 %. Service unit tests with Mockito (repositories, clients) and WireMock for HTTP clients; `@DataJpaTest` for non-trivial repository queries. Integration tests with Testcontainers plus WireMock. **Provider contract tests**: every provided operation and event validates against `contracts/provided/*`. **Consumer contract tests**: every consumed operation and event, parsed from `contracts/consumed/*` snapshots and fixtures. Event tests: outbox row and envelope; consume a fixture **twice** (idempotency). Concurrency: ≥ 100 threads for money and limits code. |
| Local gates | Per service: `./gradlew check` (tests, ArchUnit, coverage, OpenAPI drift against `contracts/provided/openapi.yaml`, lock verification). Repo-wide: `make verify` (isolation, build template, versions, one scope per branch, `contracts.py check`). CI/CD, Helm, k6/Gatling, E2E and observability stacks are **deferred** in this phase. |
| Git | Trunk-based. One scope per branch: `<svc>/wp-<n>-<slug>`, `<svc>/<module>/wp-<n>-<slug>`, `cr/<CR-id>-<svc>`, `build/<slug>`. Conventional Commits with the service as scope. The code owner reviews. Agents never merge. |
| Modular services | wallet (`wallet` + `partner`), pricing (`pricing` + `campaign`), finance-ops (`reconciliation` + `reporting`), admin (`governance` + `notification`). Modules are top-level packages, each with the full layer set inside (`<module>.controller`, `<module>.service`, …), plus a service-private `common` package (shared config, exception, messaging, clients). A module calls another only through that module's public `<module>.service.<Module>Facade` interface and its `<module>.dto` records, enforced by `ArchitectureTest`. The service has one outbox and one `/v1/approvals` engine. The second module prefixes its tables (`partner_`, `campaign_`, `reporting_`, `notif_`) and uses its own inbox `<module>_processed_event`. Flyway: one location and one history table per module. No Spring Modulith. |

## K10. Global Definition of Done (each service adds its own in SPEC §12)

- [ ] Every WP in SPEC §10 done; `docs/PROGRESS.md` complete.
- [ ] Every provided operation and event implemented and provider-contract-tested against `contracts/provided/*`.
- [ ] Every consumed operation and event stubbed or fixture-tested from `contracts/consumed/*`; switched to real services in the Compose stack.
- [ ] Swagger reachable through the edge proxy; generated OpenAPI matches `contracts/provided/openapi.yaml` (drift check green).
- [ ] Flyway runs idempotently from an empty `svc_<name>`; a test proves the role cannot read another schema.
- [ ] `make verify` green; the service builds alone (`cd services/<svc> && ./gradlew clean check`).
- [ ] Healthy in the Compose stack within its `mem_limit`.
- [ ] Metrics from SPEC §9 exposed; no PII in logs (log-scan test).
- [ ] SRS IDs traced to tests (`docs/TRACEABILITY.md`).

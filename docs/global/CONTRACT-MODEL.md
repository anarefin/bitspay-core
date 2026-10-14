# Contract Model — producer-owned contracts, consumer pins

**Model version: 1.0.** This file defines how a service declares what it **provides** and what it **consumes**, so that:

1. a Claude Code session for one service has everything it needs **inside that service's folder** (plus `00-global/`), and
2. a change to one service touches only that service, plus the consumers that actually use the changed fields.

## 1. Ownership rules

| # | Rule |
|---|---|
| O1 | **The producer owns its contract.** Every REST operation, event type, code list, cache/data format and problem `reason` has exactly one owner, the service that serves or emits it. Only the owner edits it, in `services/<owner>/contracts/provided/`. |
| O2 | **Producers never list consumers.** A producer's pack does not name the services that read its topics or call its APIs (no consumer columns, no group ids of others). The exception is an **authorisation** list (e.g. ledger's allowed callers per command), which is the producer's own policy. |
| O3 | **Consumers declare exactly what they use.** For each dependency, a consumer pins the producer, the artefact, the major version (API path major / `eventVersion`), the producer `contractVersion` it was written against, and the **fields it reads** (`fieldsUsed`) and the **codes it branches on** (`codesUsed`). |
| O4 | **Tolerant reader.** Consumers ignore unknown fields and handle unknown enum values safely. So any **additive** producer change (minor version) needs no consumer change. |
| O5 | **Consumer snapshots.** `contracts/consumed/<producer>/` holds a generated copy of the exact producer artefacts at the pinned version. A consumer session reads only its own folder. The snapshot is refreshed **only** when the consumer re-pins. |
| O6 | **Inbound topics.** `notification.requests`, `approval.events` and `audit.events` are written by many services into admin-service. admin-service owns their schemas (`provides.inboundTopics`). Every writer pins them under `consumes.inboundTopics`. |
| O7 | **No cross-pack edits.** A service that needs something from another service raises a change request **to that service** (CHANGE-PROCESS kind D). It never edits the other pack. |
| O8 | **Registries are generated, not owned.** System-wide lists (all topics, all group ids, all entity types, all templates, all txnRef prefixes) are **generated** into `00-global/DEPENDENCY-INDEX.md` from the packs. Nobody edits them by hand. |

## 2. Pack file layout

```
services/<NN>-<service>/
  SPEC.md  CLAUDE.md
  changes/CR-<SVC>-<n>.md
  contracts/
    contract.yaml                                   # the manifest (this document)
    provided/openapi.yaml                           # OpenAPI 3.1 — every operation this service serves (incl. staff/internal)
    provided/events/<topic>/<EVENT_TYPE>.v<n>.schema.json   # JSON Schema 2020-12 of envelope.data
    provided/events/<topic>/<EVENT_TYPE>.v<n>.example.json  # one valid full envelope
    provided/codes.yaml                             # code sets, problem reasons/extensions, entity types, templates, …
    provided/data/<id>.v<n>.(md|json|schema.json)   # non-HTTP data contracts (cache formats, algorithms, golden vectors)
    consumed/<producer-service>/...                 # GENERATED snapshot (contracts.py snapshot) — never hand-edited
  stubs/<producer-service>/*.json                   # WireMock mappings (generated from consumed/, hand-tuned allowed)
  fixtures/events/<topic>.<EVENT_TYPE>.jsonl        # produced + consumed event examples
```

## 3. `contract.yaml` — the manifest

```yaml
service: transaction-service          # bare spring.application.name
number: "02"
modules: []                           # e.g. [wallet, partner] for merged services
contractVersion: 1.0.0                # semver of everything under provided/ (see CHANGE-PROCESS §2)
kernel: "1.0"                         # 00-global/GLOBAL-CONVENTIONS.md version written against
owner: Dev-2                          # human owner (approves kind A/B changes)

provides:
  apis:
    - openapi: provided/openapi.yaml
      major: 1                        # path major (/v1)
      # every operation in the openapi is provided; internal/staff-only ones carry x-audience: internal|staff|service
  events:
    - topic: txn.events
      key: "sender (from) walletId; REVERSED/REFUNDED: the original's from walletId"
      compacted: false
      tombstones: false
      partitions: {dev: 3, prod: 96}
      retention: 7d
      transport: outbox               # outbox | direct (only ledger.changes)
      eventTypes:
        - {type: TRANSACTION_COMPLETED, version: 1, aggregateType: Transaction,
           schema: provided/events/txn.events/TRANSACTION_COMPLETED.v1.schema.json}
  inboundTopics: []                   # admin-service only (O6): same shape as events
  data:
    - {id: wallet-status-cache, version: 1, file: provided/data/wallet-status-cache.v1.md, kind: redis-format}
  codes: provided/codes.yaml

consumes:
  apis:
    - producer: wallet-service
      operation: "GET /v1/wallets/{walletId}/status"   # exactly as in the producer openapi
      major: 1
      pinnedContractVersion: 1.0.0
      purpose: "fallback when the Redis status cache misses"
      fieldsUsed: ["path.walletId", "res.status", "res.type", "res.kycTier"]
      codesUsed: [{set: walletStatus, values: "*"}]
      resilience: {timeoutMs: 150, circuitBreaker: true, onFailure: "503 DEPENDENCY_UNAVAILABLE"}
  events:
    - producer: wallet-service
      topic: wallet.events
      eventType: WALLET_UPSERTED
      version: 1
      pinnedContractVersion: 1.0.0
      groupId: transaction-service.wallet
      purpose: "..."
      fieldsUsed: ["walletId", "status", "type"]      # paths inside envelope.data
      codesUsed: []
  inboundTopics:
    - owner: admin-service
      topic: notification.requests
      eventType: NOTIFICATION_REQUESTED
      version: 1
      pinnedContractVersion: 1.0.0
      fieldsUsed: ["*"]                               # writers use the whole schema
      templates: [TXN_RECEIPT]                        # template codes this service sends (declared in its own codes.yaml)
  data:
    - {producer: wallet-service, id: wallet-status-cache, version: 1, pinnedContractVersion: 1.0.0, fieldsUsed: ["*"]}
  codes:
    - {producer: admin-service, set: refdataType, values: [SYSTEM_PARAM]}
  refdata:                                            # refdata items read from admin-service refdata.events
    - {type: SYSTEM_PARAM, codes: ["FEATURE.P2P", "CUTOFF.EOD"]}
```

### 3.1 `fieldsUsed` path syntax

| Prefix | Meaning | Example |
|---|---|---|
| *(events)* none | path inside `envelope.data` | `amountPoisha`, `legs[].accountId`, `partyRef.walletId` |
| `path.` | path parameter | `path.walletId` |
| `query.` | query parameter | `query.cursor` |
| `header.` | request header specific to the operation | `header.Idempotency-Key` |
| `req.` | JSON request body | `req.amountPoisha`, `req.metadata.initiatorActorId` |
| `res.` | JSON body of the success (2xx) response | `res.status`, `res.items[].txnRef` |
| `problem.` | problem+json extension member (beyond kernel fields) | `problem.transaction`, `problem.limitCode` |
| `*` | **the whole artefact**: sinks and archivers that store everything | `"*"` |

- `[]` marks an array element.
- A path that names an object means the consumer reads **the whole object**.
- **Request fields count as used** because the consumer sends them. A producer that removes or renames a request field breaks that consumer. A new *optional* request field breaks no one.

### 3.2 `codesUsed`

`{set: <codeSet name in the producer's codes.yaml>, values: [..] | "*"}`. Special set names: `entityTypes` (the producer's maker-checker entity types) and `reason:<Group>` (a `reasonCodes` group, e.g. `reason:Hold`). Kernel enums (e.g. `feeBearer`, problem `code`) are never listed — they belong to no producer. Declare a set whenever the consumer **switches** on its values. A producer adding a value is additive. Removing or renaming a value impacts only the consumers that list it, or that list `"*"`.

## 4. `codes.yaml` — owned code lists

```yaml
codeSets:                     # enums other services may branch on
  walletStatus:
    description: "Wallet status, single-letter codes on the wire (requests accept letter or name)"
    values:
      - {code: A, name: ACTIVE, description: "..."}
problemReasons:               # provider-owned values of problem.reason
  - {code: STATE_CONFLICT, reason: HAS_ACTIVE_DESCENDANTS, operations: ["POST /v1/partners/{partnerId}/status-changes"], extensions: [activeDescendants]}
problemExtensions:            # provider-owned extension members of problem+json
  - {name: activeDescendants, type: int32, when: "reason = HAS_ACTIVE_DESCENDANTS"}
entityTypes:                  # maker-checker entityType values (K5), per module
  - {module: partner, values: [Partner, PartnerApplication]}
notificationTemplates:        # templates THIS service sends on notification.requests (K4.4)
  - code: WALLET_CLOSURE_REQUESTED
    category: SERVICE         # SECURITY|TRANSACTIONAL|SERVICE|INTERNAL|REMINDER|MARKETING
    recipient: "wallet holder (walletId)"
    variables:
      - {name: walletId, type: TEXT, req: true, notes: "..."}
reasonCodes:                  # governance REASON_CODE items this service introduces (seeded by admin from here)
  - {group: "Wallet status", values: [KYC_APPROVED, DORMANCY]}
txnRefPrefixes:               # reference prefixes this service mints (uniqueness checked globally)
  - {prefix: PP, meaning: "P2P payment", format: "{prefix}{yyMMdd}00{8 Crockford}"}
productCodes: [P2P, CASH_IN]  # FEATURE.<PRODUCT> codes this service honours (K3.7)
metrics:                      # bitspay_<service>_* names that dashboards/alerts depend on
  - {name: bitspay_transaction_payments_total, type: counter, labels: [txn_type, status, failure_code]}
```

## 5. Versioning

| Artefact | Version carrier | Additive (minor) | Breaking (major) |
|---|---|---|---|
| Pack | `contractVersion` semver | MINOR+1 on any additive provided change; PATCH for editorial fixes (descriptions, examples) | MAJOR+1 when any artefact gets a new major |
| REST | path major `/v1` | new operation, new optional request field, new response field, new enum value, new `reason` | remove/rename a field or operation, type change, optional→required, narrower validation, changed semantics → serve `/v2` alongside `/v1` |
| Event | `eventVersion` (filename `.v<n>.`) | new optional `data` field, new enum value, new eventType on the topic | anything else → emit `.v<n+1>` alongside `.v<n>` (dual-publish) until no consumer pins `.v<n>` |
| Code set | the pack's `contractVersion` | new value | removed/renamed value |
| Data contract | `version` in the manifest, `.v<n>.` in the file name | additive field | anything else |

## 6. Tool — `00-global/tools/contracts.py`

| Command | What it does |
|---|---|
| `check [<svc>…]` | Validates manifests, JSON Schemas, OpenAPI parse + operation ids, examples against schemas, pins resolve, every `fieldsUsed` path exists in the producer's **current** artefact of the pinned major, codes unique (txnRef prefixes, problem reasons per code, group ids), O2 (no consumer lists in producers). Exit 1 on error |
| `snapshot <svc>` | Copies pinned producer artefacts into `<svc>/contracts/consumed/<producer>/` and writes `consumed/PINS.lock` |
| `index` | Regenerates `00-global/DEPENDENCY-INDEX.md` (+ `generated/*.json`) |
| `impact <svc> <artefact>[#field]` | Lists consumers affected by a change. Artefact: `"GET /v1/..."`, `<topic>/<EVENT_TYPE>`, `codes/<set>`, `data/<id>` |
| `cr new <svc> "<title>"` · `cr analyse <CR-id>` · `cr verify <CR-id>` · `cr log` | Change-request lifecycle (CHANGE-PROCESS.md) |

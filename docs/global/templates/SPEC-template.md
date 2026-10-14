# SVC-<NN> — <service-name> — Service Specification (v6)

<!-- TEMPLATE RULES (delete this comment in a real spec)
- ONE clean text. No overlays, no "v1.x alignment" callouts, no "superseded" ADRs, no "Part 0 reading rules", no "until CCR-x" fallbacks. State the current truth only; history lives in §14 (Changelog) and §13 (provenance notes, one line each).
- Self-contained for a Claude Code session that can read ONLY this folder + ../../00-global/. Never write "see catalogue §x" or "see SVC-yy": restate what is needed. The only allowed outward references: 00-global/GLOBAL-CONVENTIONS.md (K-sections), 00-global/CONTRACT-MODEL.md, 00-global/CHANGE-PROCESS.md, and this pack's contracts/ files.
- §5 is the human-readable mirror of contracts/provided/*. §6 is the mirror of contract.yaml `consumes` (+ the payload subset actually used, copied from the producer's contract at the pinned version).
- Open human decisions: write the provisional value and tag inline "OPEN D-xx"; list every tag in §13.
- Diagrams: Mermaid only (flowchart, sequenceDiagram, stateDiagram-v2, erDiagram, classDiagram). Every §3.1 edge label names the contract artefact + version.
-->

| Field | Value |
|---|---|
| Service | `<service-name>` (`spring.application.name`) |
| Number / owner | SVC-<NN> · <Dev-x> (modules: <module → owner>) |
| Layer / release | <Core / Ledger & data / Back office> · R1 / R2 |
| contractVersion | 1.0.0 (see `contracts/contract.yaml`) |
| Kernel | 1.0 (`../../00-global/GLOBAL-CONVENTIONS.md`) |
| Ports | HTTP 81NN · management 91NN |
| Schema / role | `svc_<name>` |
| Depends on (pins) | <producer@major — one line per producer> |
| Open decisions | <OPEN D-xx list> |

## 1. Mission and boundaries
### 1.1 Mission (plain English, one worked example with the Rahim/Karim/Salma/Nirob Store cast)
### 1.2 In scope
### 1.3 Out of scope / deferred (table: deferred item → replacement now)
### 1.4 This service must NEVER (numbered)
### 1.5 Modules (merged services only: module → responsibility, package root, owner, table prefix)

## 2. SRS traceability
| SRS ID | Requirement (short) | Covered by (BR / WP / API / event) |

## 3. Architecture
### 3.1 Context diagram
```mermaid
flowchart LR
  %% this service in the middle; one node per direct neighbour; edges labelled "<artefact> v<major>"
```
### 3.2 Component diagram (inside the service)
```mermaid
flowchart TB
  %% layered (K9): controller → service → repository (JPA) / client (Http<Svc>Client, redis, object store) / messaging (outbox, kafka consumers); entity, dto, mapper alongside; modules as subgraphs talking via <module>.service facades
```
### 3.3 Runtime and deployment (Compose)
Ports, profiles, roles/processes, `mem_limit`, schema `svc_<name>`, Redis/TB/ClickHouse use, env vars beyond kernel K8.3, consumer groups, scheduled jobs.
### 3.4 Key flows (sequence diagrams — one per main use case, incl. failure/unknown-outcome paths)
### 3.5 State machines (stateDiagram-v2 per stateful entity)
### 3.6 Architecture decisions (ADR-xx: decision · why · consequence — current decisions only)
### 3.7 Latency / throughput budget (hot-path services)

## 4. Data model
### 4.1 Tables (Flyway `V1__init.sql` … full DDL incl. outbox/processed_event per kernel K8.2)
### 4.2 Redis keys / caches (if any)
### 4.3 Retention and archival

## 5. Provided contracts  (mirror of `contracts/provided/` — artefact wins on conflict)
### 5.1 REST operations
Summary table: | Operation | Audience (customer/partner/staff/service/internal) | Actors & roles | Idempotency | Purpose |
Then per operation:
#### 5.1.x `METHOD /v1/...`
- Actors, Idempotency, pagination
- Request: field table `Field | Type | Req | Null | Constraints / enum | Notes` + JSON example
- Response 2xx: field table + JSON example
- Errors: | HTTP | code | reason | extensions | when |
### 5.2 Events produced
Topic table: | Topic | Key (= aggregateId) | Compacted / tombstones | Partitions dev/prod | eventTypes |
Per eventType: aggregateType, when emitted, ordering/keying notes, `data` field table, full envelope JSON example.
### 5.3 Owned codes (mirror of `codes.yaml`): code sets, problem reasons & extensions, entityTypes, notification templates (+ variables), reason codes, txnRef prefixes, product codes
### 5.4 Data contracts (non-HTTP: cache formats, shared algorithms, golden vectors)

## 6. Consumed contracts  (mirror of `contract.yaml → consumes`)
Summary table: | Producer | Artefact | Pinned (major / contractVersion) | Fields used | Why |
### 6.x <producer> — <artefact>
- Pin, purpose, when called / consumed
- Payload subset used: field table of ONLY the fields in fieldsUsed (types copied from the producer contract)
- Outbound headers / forwarded context
- Resilience: timeout, retries, circuit breaker, bulkhead; failure behaviour (what the service does / returns)
- Events: consumer group, filter, idempotency (inbox), ordering assumptions, DLQ
- Stub / fixture file names (stubs/<producer>/…, fixtures/events/…)
### 6.y Inbound topics written (notification.requests / approval.events / audit.events) — templates sent, entityTypes, audit actions
### 6.z Reference data read (refdata types/codes + fallback values)

## 7. Business rules and calculations
BR-<SVC>-nn, grouped by capability; formulas with worked numeric examples; idempotency and concurrency rules.

## 8. Configuration
| Property | Default | Meaning | Provisional / OPEN D-xx |

## 9. Non-functional requirements
Throughput (design target 5k TPS sustained system-wide; this service's share), latency p95/p99, availability, mem_limit, metrics (names + labels), logging/PII, security.

## 10. Work packages (build order for Claude Code)
### WP-1 Skeleton & contracts (every pack: project, Flyway V1 with outbox/inbox, ActorContext, problem model, provided OpenAPI served, stubs + fixtures wired, contract tests red→green)
### WP-n … (each: goal · scope · acceptance tests · depends on (only own earlier WPs or stubs))

## 11. Test plan
Provider contract tests · consumer contract tests (from contracts/consumed snapshots) · unit/property · integration (Testcontainers) · event idempotency (deliver twice) · concurrency · golden vectors · manual Compose scenarios.

## 12. Definition of done (additions to kernel K10)

## 13. Open decisions, deferred items, assumptions
| Tag | Topic | Provisional value used | Where used |
Deferred CCRs (with interim behaviour) · assumptions · provenance notes (one line: source spec/catalogue/audit ids consolidated).

## 14. Changelog
| contractVersion | Date | CR | Change |
| 1.0.0 | 2026-10-13 | — | v6 baseline consolidated from SVC-<NN> v1.2 + v5.0 overlay + catalogue v1.4 + contract audit + GL CCRs |

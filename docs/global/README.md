# Bits Pay — Service Specs v6

There are 12 independent service packs. Each pack can be built by its own Claude Code session, reading only its own folder plus `00-global/`. Every pack carries:
- its own **architecture diagrams**: context, components, sequences, states, ER
- its **full spec**
- the **complete payloads it produces and consumes**

Contracts are **owned by the producer** and **pinned by the consumer**, so changing one service touches only the services that actually read what changed.

## What changed from v5.0

| v5.0 | v6 |
|---|---|
| Base spec (v1.2) + v5.0 overlay + "v1.1 alignment" callouts + Part 0 (merged services) | **One clean SPEC.md per service.** The current truth only; history goes in the changelog |
| One central 5,500-line Contract Catalogue (v1.4); 263 audit edits not yet applied to the specs | Each contract lives in its **owner's** `contracts/provided/` (OpenAPI 3.1, JSON Schema, `codes.yaml`). All audit edits are applied |
| Central registries (consumer lists, group ids, entity types, templates, reason codes, txnRef prefixes, problem extensions) | Each owner declares its own entries. System-wide lists are **generated** (`DEPENDENCY-INDEX.md`, `generated/*.json`) |
| Consumers read the catalogue | Consumers **pin** `producer + artefact + major + contractVersion + fieldsUsed`, with a snapshot in `contracts/consumed/` |
| GL addendum patched three other services (proposed CCRs) | CCR-GL-01..08 applied: general-ledger-service owns the CoA and the GL export |
| Contract change = `[ccr]` MR on the catalogue, with every owner reviewing | Change request in the **owning pack**. `contracts.py cr analyse` names the exact impacted consumers; nobody else is opened |

## Layout

```
Service Specs v6/
├── 00-global/
│   ├── README.md                 ← you are here
│   ├── GLOBAL-CONVENTIONS.md     the kernel: headers, errors, envelope, outbox, money, hashing, roles, standards (v1.0)
│   ├── CONTRACT-MODEL.md         how packs declare provides/consumes; fieldsUsed syntax; versioning
│   ├── CHANGE-PROCESS.md         step-by-step procedure to change a service (CR lifecycle, adoption)
│   ├── CR-LOG.md                 every change request and its state
│   ├── SYSTEM-CONTEXT.md         service table + layered diagram + generated dependency graph
│   ├── DEPENDENCY-INDEX.md       GENERATED: who pins what, topics, consumer groups, REST usage
│   ├── MIGRATION-SOURCES.md      provenance: which v5.0 sources each pack was consolidated from
│   ├── MIGRATION-REPORT.md       coverage report of the consolidation
│   ├── schemas/                  kernel JSON Schemas (envelope, problem, money, page)
│   ├── templates/                SPEC, CLAUDE, CR templates; pack-authoring brief
│   ├── generated/                GENERATED registries (templates, reason codes, product codes, entity types, …)
│   └── tools/contracts.py        check | snapshot | index | impact | cr new/analyse/verify/log
└── services/<NN>-<service>/
    ├── SPEC.md  CLAUDE.md
    ├── changes/                  CR-<SVC>-<n>.md for this service
    ├── contracts/
    │   ├── contract.yaml         manifest: provides + consumes (pins, fieldsUsed, group ids)
    │   ├── provided/             openapi.yaml · events/<topic>/<TYPE>.v1.schema.json + example · codes.yaml · data/
    │   └── consumed/<producer>/  GENERATED snapshots of pinned producer artefacts (+ PINS.lock)
    ├── stubs/<producer>/         GENERATED WireMock mappings for every consumed operation
    └── fixtures/events/          GENERATED event fixtures (produced + consumed)
```

## Building a service with Claude Code

1. Copy `services/<NN>-<service>/` into the repo as `bitspay-core/services/<service>/docs/` (or keep this tree as `docs/specs/`), and `00-global/` as `bitspay-core/docs/global/`. The relative path `../../00-global/` used inside the packs must still resolve; otherwise adjust it once in CLAUDE.md.
2. Start a session scoped to the service (`scripts/agent <service>`) and run, in plan mode:
   > Read CLAUDE.md, SPEC.md, contracts/contract.yaml and ../../00-global/GLOBAL-CONVENTIONS.md. We are doing WP-1 from SPEC.md §10. Propose a plan, then implement it with tests. Do not change anything under contracts/.
3. Repeat for each work package. Build against `stubs/` and `fixtures/`; never against another service's code.

## Changing a service

Follow `CHANGE-PROCESS.md`:
1. Classify the change.
2. `cr new`.
3. `cr analyse`, which writes the Adoption Plan.
4. Get approval.
5. Apply the change to the producer.
6. Re-pin only the consumers the plan lists.
7. `cr verify`.

## Tool quick reference

```bash
python3 00-global/tools/contracts.py check                 # all packs
python3 00-global/tools/contracts.py check wallet-service  # one pack
python3 00-global/tools/contracts.py snapshot all          # refresh consumed/ snapshots, stubs, fixtures
python3 00-global/tools/contracts.py index                 # regenerate DEPENDENCY-INDEX.md, SYSTEM-CONTEXT graph, generated/*
python3 00-global/tools/contracts.py impact transaction-service "txn.events/TRANSACTION_COMPLETED#amountPoisha"
python3 00-global/tools/contracts.py cr new wallet-service "Add nickname to WALLET_UPSERTED"
```

Requires Python 3.9+ and PyYAML. Diagram check: `MERMAID_NODE_MODULES=<dir with mermaid@11> node 00-global/tools/mermaid-check.mjs services/*/SPEC.md`.

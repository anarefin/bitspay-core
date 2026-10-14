# Pack authoring brief (for the agent that writes one service pack)

You are writing **one** v6 service pack under `Service Specs v6/services/<NN>-<service>/`. Work only inside that folder.

## Read first
1. `../../00-global/GLOBAL-CONVENTIONS.md`: the kernel. Do not restate kernel rules in full. Reference them as "kernel K3.3" etc. and state only service-specific deltas.
2. `../../00-global/CONTRACT-MODEL.md`: the exact format of `contract.yaml`, `codes.yaml`, `fieldsUsed` and the file layout.
3. `../../00-global/templates/SPEC-template.md` and `CLAUDE-template.md`: the structure to follow.
4. `../../00-global/MIGRATION-SOURCES.md`: your sources, line ranges, precedence, and the ownership decisions table.

## Deliverables (all inside your pack folder)

| File | Content |
|---|---|
| `SPEC.md` | The full spec, following the template exactly (§0 header table, §1–§14). One clean text: **no overlays, no "v1.x alignment" callouts, no superseded ADRs, no "Part 0 reading rules", no Maven, no Helm/CI/E2E/k6 as current scope.** Carry over **all** substantive content of the old spec (BRs, DDL, state machines, algorithms, config, WPs, tests), rewritten to the current truth (CAT v1.4 + AUD §4 edits + GL CCRs + v5.0 overlay rules). Do not summarise away detail: a developer and Claude Code must be able to build the service from this file alone. |
| `CLAUDE.md` | From the CLAUDE template, filled with service-specific rules. |
| `contracts/contract.yaml` | Manifest per CONTRACT-MODEL §3. `contractVersion: 1.0.0`, `kernel: "1.0"`. **Every** consumed operation, event, inbound topic, data contract, code set and refdata item, each with precise `fieldsUsed`. |
| `contracts/provided/openapi.yaml` | OpenAPI **3.1**. Every operation this service serves: service-to-service, staff/back-office, internal/test. Mark each with `x-audience: service \| staff \| customer \| partner \| internal` and `x-actors` (allowed actor types and roles; for service callers, the allowed `X-Actor-Id` values). Typed request and response schemas (components), the error responses with `application/problem+json`, and `reason` enums/extension members per operation. Include at least one `example` per request and per 2xx response (used to generate WireMock stubs). Path parameter names must be **exactly** as in the catalogue headings (e.g. `{walletId}`, `{txnRef}`, `{commandId}`). |
| `contracts/provided/events/<topic>/<EVENT_TYPE>.v1.schema.json` | JSON Schema 2020-12 of `envelope.data`, for each eventType you produce. Set `additionalProperties: true`, list `required` (= Req Y), and allow `null` types where Null = Y. Use `$id` `https://bitspay.local/schemas/<service>/<topic>/<EVENT_TYPE>.v1.schema.json`. |
| `contracts/provided/events/<topic>/<EVENT_TYPE>.v1.example.json` | One **full envelope** example that validates. |
| `contracts/provided/codes.yaml` | Per CONTRACT-MODEL §4. Only the sections that apply. |
| `contracts/provided/data/*` | Non-HTTP data contracts, if you own any (see the ownership table). |
| `fixtures/events/` | Leave empty (the tool generates them). |
| `stubs/` | Leave empty (the tool generates them). |

## Rules that make the packs independent

1. **Producer-owned (O1).** Put in `provided/` only what this service serves or emits. Never describe another service's payloads as yours.
2. **No consumer lists (O2).** Your provided artefacts and SPEC §5 never name who consumes your topics or calls your APIs. Two exceptions: (a) authorisation lists in `x-actors`; (b) SPEC §3.1, the context diagram, which may show neighbours on both sides.
3. **Consumers declare what they use (O3).** For each dependency, SPEC §6 shows the **subset** of fields you use: the field table copied from the producer's contract (CAT v1.4 / GLA). `fieldsUsed` must name **exactly** those fields, using the path syntax in CONTRACT-MODEL §3.1, with paths exactly as in CAT. Use `"*"` only for true sinks that store everything (reporting ingestion, governance audit chain).
4. **Inbound topics (O6).** If you send notifications, approvals or audits, list them in `consumes.inboundTopics`, pinned to admin-service 1.0.0. Templates you send go in **your** `codes.yaml → notificationTemplates`, with the variables table copied exactly from CAT §8.6.1 group C<n> (or GLA). Your maker-checker entity types go in `codes.yaml → entityTypes`.
5. **Pins.** Every pin uses `pinnedContractVersion: 1.0.0` and `major: 1` / `version: 1`.
6. **Group ids.** Take consumer group ids from CAT §12.1 (with GLA §12.1) and put them in your `consumes.events[].groupId`.
7. **Self-contained text (no outward references).** Do not write "see catalogue §x", "see SVC-yy" or "per the owner spec". Restate what is needed. Allowed references: kernel K-sections, CONTRACT-MODEL, CHANGE-PROCESS, and your own `contracts/` files.
8. **Open decisions.** Where CAT says "pending architect sign-off" or "⚠ open: D-xx", write the v1.4 value and tag it `OPEN D-xx` inline. List every tag in §13 (tag · topic · provisional value · where used).
9. **Diagrams (Mermaid only).**
   - §3.1 context: a `flowchart LR` with this service in the centre. Each edge is labelled with its artefact and major, e.g. `"POST /v1/ledger/commands/{name} v1"` or `"txn.events v1"`, and both provided and consumed edges appear.
   - §3.2 components: a `flowchart TB` of the K9 layers — controller → service → repository (JPA) / client (http clients, redis, TB, ClickHouse, object store) / messaging (outbox, inbox consumers) — with modules as subgraphs connected only through `<module>.service` facades.
   - §3.4: one `sequenceDiagram` per key flow.
   - §3.5: one `stateDiagram-v2` per stateful entity.
   - §4: an `erDiagram` for the main tables.
   - Keep Mermaid syntax simple and valid: quote labels containing `{}`, `/`, `()` or `:`, and avoid `;` inside labels.
10. **Applying the audit.** Apply every AUD §4 edit for your service. Where the old spec contradicts CAT v1.4, CAT wins. Examples must follow CAT v1.4: canonical UUIDs (no `t-…` IDs), 3-digit milliseconds, MONEY variables as int64 poisha, never pre-formatted.
11. **Changelog.** §14 gets one baseline row only. §13 ends with a short "Provenance" list naming the sources consolidated: old spec version, CAT v1.4 sections, AUD C-ids applied, CCR-GL ids applied.
12. **Quality bar.** Every provided operation and event has a field table in §5 **and** a schema in `provided/`, and the two must agree. Validate JSON and YAML before finishing:
   - `python3 -c "import json,sys;[json.load(open(f)) for f in sys.argv[1:]]" $(find contracts -name '*.json')`
   - `python3 -c "import yaml;yaml.safe_load(open('contracts/contract.yaml'));yaml.safe_load(open('contracts/provided/openapi.yaml'));yaml.safe_load(open('contracts/provided/codes.yaml'))"`
13. **Size.** A full pack is long; that is expected. Write SPEC.md in several appends if needed. You may copy large unchanged blocks from the old spec with shell tools (`sed -n 'a,bp'`), then edit them. Read the old spec and the CAT slices fully before writing.

## Final report (your last message, ≤ 300 words)
- Files written, with line counts.
- Counts: provided operations, produced eventTypes, consumed operations, consumed eventTypes.
- Any place where you had to guess, or where sources conflicted and the conflict is not resolved by the precedence rule.
- Any field or operation another service must provide that you could not find in CAT/GLA (possible kind-D gaps).

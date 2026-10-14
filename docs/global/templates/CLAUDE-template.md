# <service-name> — agent instructions

You are implementing **<service-name>** of Bits Pay. This folder is the whole world for this service.

## Read first (every session)
1. `SPEC.md` — the specification (one clean text; §10 lists work packages).
2. `contracts/contract.yaml` — what this service provides and consumes (pins).
3. `contracts/provided/*` — binding API/event/code contracts this service owns.
4. `contracts/consumed/*` — snapshots of everything this service uses from others (read-only).
5. `../../00-global/GLOBAL-CONVENTIONS.md` — kernel rules (headers, errors, envelope, outbox, money, testing).

## Commands
- `./gradlew check` · `./gradlew test --tests 'X'` · `./gradlew integrationTest` · `./gradlew bootRun --args='--spring.profiles.active=local'` · `./gradlew openApiUpdate`
- From repo root: `make rebuild svc=<service-name>`, `make hybrid svc=<service-name>`, `make verify`
- Contracts: `python3 ../../00-global/tools/contracts.py check <service-name>`

## How to work
- One work package per session, plan mode first: "We are doing WP-n from SPEC.md §10. Propose a plan, then implement it with tests."
- Contract-first: implement `contracts/provided/*` exactly; consume others only via `contracts/consumed/*`, `stubs/` and `fixtures/` — never read or import another service's code.
- Finish each WP with `./gradlew check` green, OpenAPI drift check green, `docs/PROGRESS.md` updated, `make verify` green.

## Non-negotiable rules
- Edit only this folder. DB schema `svc_<name>` only. One outbox `svc_<name>.outbox`.
- Money is `long` poisha; <service-specific money/ledger rules>.
- <5–10 service-specific rules from SPEC §1.4 / §7>
- PII never in logs; mask per kernel K2.

## Never change without a change request (`../../00-global/CHANGE-PROCESS.md`)
- Anything under `contracts/provided/` or `contracts/consumed/`, `contract.yaml` pins, `codes.yaml`.
- If a WP seems to need a contract change: stop, write `changes/CR-<SVC>-<n>.md` (template in `../../00-global/templates/`), and tell the developer.

## Code map
`com.bracits.bitspay.<pkg>` — controller / dto / service / repository / entity / mapper / exception / client / messaging / config (kernel K9 layered layout) <modules>

## Testing expectations
Provider contract tests against `contracts/provided/*`; consumer tests from `contracts/consumed/*`; events consumed twice; ≥100-thread concurrency tests on money/limit paths; <service-specific>.

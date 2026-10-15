---
name: start-wp
description: Plan one Bits Pay work package (SPEC §10) for one service. Plan only — writes no code.
argument-hint: <service> <WP-n>
disable-model-invocation: true
---
# Start a work package (plan only)

Input: `$ARGUMENTS` = `<service> <WP-n>`, e.g. `wallet-service WP-3`. Below, SVC is the service and WP the work package. `services/SVC/` is relative to the `bitspay-core/` root; if the session already runs inside `services/SVC/`, use paths relative to it.

Do NOT create, edit or delete any file in this step. If an argument is missing, ask for it and stop.

0. Run `scripts/scope.sh status` (from `bitspay-core/`; `../../scripts/scope.sh status` inside `services/SVC/`). It must print `Scope locked to SVC`. If not, stop and ask the developer to run `make lock svc=SVC` — never run it yourself.
1. Read `services/SVC/CLAUDE.md` and follow its "Read first" order. Read whole sections, not snippets:
   - `docs/SPEC.md` §10 entry for WP (scope, acceptance, depends-on) and every section it points to (§3, §4, §5, §7 …).
   - `docs/SPEC.md` §11 rows with test names that belong to WP, §12, and §13 rows that touch WP.
   - The `docs/contracts/provided/*` and `docs/contracts/consumed/*` files this WP implements or calls.
   - The kernel rules in `docs/global/GLOBAL-CONVENTIONS.md` this WP touches.
   - `docs/PROGRESS.md` and the current code under `src/`.
2. Check that every "Depends on" WP is `done` in `docs/PROGRESS.md`. If not, stop and report which.
3. Output the plan under these headings:
   - **Scope** — 3–6 bullets, each citing SPEC refs (§x.y, BR-…).
   - **Files** — every file to create or change, with its package. Kernel K9 layers only: controller, dto, service, repository, entity, mapper, exception, client, messaging, config.
   - **Tests first** — every binding test name from the WP acceptance and SPEC §11, with its class, `*Test` or `*IT`, and what it asserts.
   - **Migrations / config** — Flyway files, `application*.yaml` keys.
   - **Order of work** — small steps, each ending in a runnable test.
   - **Skeleton gaps** — where the generated skeleton differs from SPEC (migration names, missing build tasks such as the OpenAPI drift check) and how this WP closes them.
   - **Risks** — money, idempotency, concurrency, PII, contract shape.
   - **Open questions** — anything ambiguous or listed in §13. Never resolve by guessing; quote the §13 provisional value when one exists.
   - **Contract impact** — "none", or why a change request is needed (then recommend `/raise-cr` and stop).
4. End with: "Reply `approve` or give corrections, then run `/implement-wp SVC WP`."

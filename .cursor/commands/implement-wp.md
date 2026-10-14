<!-- Generated from .claude/skills/implement-wp/SKILL.md — edit that file, then re-run the sync loop in docs/AI-IMPLEMENTATION-GUIDE.md §8. -->
# Implement the approved work package

Input: the text typed after this command = `<service> <WP-n>`. SVC is the service, WP the work package.

Precondition: this session holds a plan for WP that the developer approved (from `/start-wp`). If not, stop and say "run /start-wp first".

Re-read `services/SVC/CLAUDE.md` now. Binding rules:
- Edit only `services/SVC/`. Never read or import another service's code — use `docs/contracts/consumed/*`, `docs/stubs/` and `docs/fixtures/`.
- Never edit `docs/contracts/**`, `contract.yaml`, `codes.yaml` or golden vectors. If the plan cannot be done without that, stop and follow `/raise-cr`.
- Kernel K9 layered packages; no ports/adapters; no interface with a single implementation unless SPEC names it (e.g. a client with Http + Fake).
- Money is `long` poisha; no `double`/`float`. No PII in logs.

For each step of the approved plan:
1. Write the failing test(s) first, using the exact binding names. Run only them (`./gradlew test --tests '<Class>'` or `./gradlew integrationTest --tests '<Class>'`) and confirm they fail for the right reason.
2. Write the minimum production code to pass. Re-run.
3. Refactor if useful; keep tests green.

Never weaken a test to make it pass. If a test contradicts SPEC, say so explicitly and ask.

When every step is done, from `services/SVC/`:
- `./gradlew check` (unit + integration tests, ArchUnit, JaCoCo ≥ 90 % on `*.service`). Fix until green. Once the OpenAPI drift check exists (added in WP-1), it is part of `check`.
- `../../scripts/contracts.sh check SVC`.

Report: steps done, tests added (names), the last lines of each gate's output, deviations from the plan and why, and what `/review-wp` should look at closely. Do not commit.

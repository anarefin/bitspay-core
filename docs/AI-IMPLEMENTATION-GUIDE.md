# AI Implementation Guide — building a Bits Pay service with Claude Code or Cursor

How to take a service from its generated skeleton (WP-0) to done, with **100 % agent-written code**. The same workflow works in Claude Code and in Cursor. The prompts ship in the repo as slash commands, so nobody pastes prompts by hand.

## 1. Ground rules

1. **Humans don't hand-write production or test code.** Developers write prompts, approve plans, review diffs and own the merge. When output is wrong, fix the *input* — the prompt, a clarification, or a change request — and re-run. Don't patch the code by hand.
2. **The pack is the source of truth.** Agents follow these, in this order of authority:
   - `services/<svc>/docs/contracts/**` (contract artefacts win any conflict)
   - `services/<svc>/docs/SPEC.md`
   - `docs/global/GLOBAL-CONVENTIONS.md` (kernel K1–K10)
   - `services/<svc>/CLAUDE.md`
3. **One work package per session.** Each WP is listed in SPEC §10, with acceptance tests and "Depends on" entries. Never batch WPs into one session.
4. **Plan → approve → implement → independent review → finish.** Every step has a command (§4).
5. **Gates decide "done", not the agent.** Before a PR can open:
   - `./gradlew check` must be green.
   - `scripts/contracts.sh check <svc>` must be green.
   - `make verify` must be green.
6. **Kernel K9 git rules:**
   - Branch `<svc>/wp-<n>-<slug>`, one scope per branch.
   - Conventional Commits with the service as scope.
   - The code owner reviews.
   - **Agents never merge.**

## 2. One-time setup

**Common to both tools**

- Install JDK 25, Docker (≈10 GB of memory), `make` and Python 3 with PyYAML.
- Run `make build && make up && make welcome` once (see [DOCKER-TUTORIAL.md](../docker/DOCKER-TUTORIAL.md)).
- Docker must be running whenever an agent works, because `*IT` tests use Testcontainers.

| | **Claude Code** | **Cursor** |
|---|---|---|
| Where to start | `cd services/<svc> && claude` (the service's `CLAUDE.md` loads at launch) | Open the `bitspay-core/` folder as the workspace |
| Agent instructions | `services/<svc>/CLAUDE.md` loads automatically | `.cursor/rules/bitspay-service.mdc` (always applied) tells the agent to read `services/<svc>/CLAUDE.md` first |
| Workflow commands | `.claude/skills/<name>/SKILL.md`, found from the parent dir; check with `/` | `.cursor/commands/<name>.md`; check by typing `/` in Agent chat |
| Plan step | Enter plan mode (**Shift+Tab**, or `claude --permission-mode plan`), then run `/start-wp` | Switch the chat to **Plan** (or Ask) mode, then run `/start-wp` |
| Implement step | Leave plan mode (Shift+Tab) → `/implement-wp` | **Agent** mode → `/implement-wp` |
| Fresh context | `/clear`, or a new terminal session | New chat (Cmd/Ctrl+N) |
| Model | Use the strongest model for `/start-wp` and `/review-wp`; a faster model is fine for `/fix-gate` | Same |
| Command auto-approval | Allow `Bash(./gradlew:*)`, `Bash(../../scripts/contracts.sh:*)`, `Bash(make verify)`, `Bash(git status)`, `Bash(git diff:*)` in your **own** `.claude/settings.local.json` | Auto-run allowlist: `./gradlew`, `make verify`, `scripts/contracts.sh`, `git status`, `git diff`. Never auto-approve `git push` or `rm` |

> These root files are hand-maintained and not generated: `.claude/skills/`, `.cursor/` and this guide. Re-running `Service Specs v6/create-skeleton.sh --force` into this folder can overwrite them, so commit them first and restore them afterwards.

## 3. What to build, in what order

**Across services (one developer owns one service).** Every service can start on day 1. Consumed APIs and events come from `docs/contracts/consumed/*`, `docs/stubs/` (WireMock) and `docs/fixtures/`, so nobody waits on another team. Ordering only matters for each service's *integration* WP (the Compose-stack WP near the end of §10), when real neighbours are needed:

| Wave | Services | Why |
|---|---|---|
| 1 | ledger, wallet, limits-risk, pricing, admin | Producers everyone consumes. `make core` runs the first four; admin supplies refdata, approvals and audit |
| 2 | transaction, treasury, disbursement, general-ledger | Need wave 1 for integration |
| 3 | compliance, support, finance-ops | Consume events from almost everything |

See `docs/global/DEPENDENCY-INDEX.md` §2 for the exact consumer → producer edges.

**Within a service:**

- Follow SPEC §10 top to bottom, respecting each WP's "Depends on".
- **WP-1 reconciles the generated skeleton with the SPEC.** The skeleton ships `V1__outbox_inbox.sql`, and the **OpenAPI drift check and `openApiUpdate` task do not exist yet**. WP-1 must add them, and from then on they are part of `./gradlew check`.

## 4. The WP loop

The example uses `wallet-service WP-3`. Commands are identical in both tools; only the mode switch differs.

| # | Step | Who | Claude Code | Cursor |
|---|---|---|---|---|
| 1 | Branch | Dev | `git switch -c wallet-service/wp-3-<slug>` | same |
| 2 | Plan | Agent | Plan mode → `/start-wp wallet-service WP-3` | Plan mode → `/start-wp wallet-service WP-3` |
| 3 | Review the plan | **Dev** | Check against §4.1, then reply `approve` or give corrections | same |
| 4 | Implement (TDD) | Agent | Shift+Tab out of plan mode → `/implement-wp wallet-service WP-3` | Agent mode → `/implement-wp wallet-service WP-3` |
| 5 | Gate failures | Agent | `/fix-gate wallet-service <gate or test>` | same |
| 6 | Independent review | Agent | `/clear` → `/review-wp wallet-service WP-3` | New chat → `/review-wp wallet-service WP-3` |
| 7 | Fix findings | Agent | Paste the BLOCKER/MAJOR rows: "Fix these findings, test-first, then re-run `./gradlew check`." | same |
| 8 | Finish | Agent | `/finish-wp wallet-service WP-3` (gates, PROGRESS.md, commit, PR text) | same |
| 9 | Push and open the PR | Dev | `git push -u origin HEAD`, then open the PR with the generated description | same |
| 10 | Code review and merge | **Dev / code owner** | Checklist in §6. Request changes go back through step 7 | same |

### 4.1 What to check in a plan (step 3)

Most bad output starts as an unreviewed plan. Reject or correct the plan when:

- **Tests:** any binding test name from the WP acceptance or SPEC §11 is missing from "Tests first".
- **Files:**
  - files outside `services/<svc>/`;
  - a package outside the K9 layers;
  - a new interface with one implementation.
- **Open questions:** an open question is "resolved" by assumption instead of by the §13 provisional value or an escalation.
- **Contract impact:** it says "none", but the plan changes a response, event or code.
- **Order of work:** a step doesn't end in a runnable test.

Correct the plan in the same session (e.g. "Add `walletCache_404_writesNegativeCache` to step 2; drop the `WalletPort` interface"). Only then approve it.

### 4.2 Prompts for situations without a command

| Situation | Prompt |
|---|---|
| Plan too big for one session | "Split this plan into WP-n.a and WP-n.b, each ending in green `./gradlew check`. Show both; implement only WP-n.a." |
| Agent drifting or repeating itself | Start a fresh session: "Continue `/implement-wp <svc> WP-n`. The approved plan is below; steps 1–3 are done (tests X, Y green). Do step 4 only." Paste the plan. |
| Need to understand the code before review | "Explain the flow of `<operation>` through controller → service → repository/client in this service, with `file:line` refs. No edits." |
| Behaviour differs from SPEC but tests pass | "SPEC §x.y says `<quote>`. The code does `<observed>`. Write a failing test that proves the gap, then fix it." |
| Coverage below 90 % | "`./gradlew check` fails on JaCoCo for `<package>`. Add meaningful tests for the uncovered branches listed in `build/reports/jacoco/`. Do not exclude classes or lower the threshold." |

## 5. When the agent must stop

| Trigger | What happens |
|---|---|
| The WP needs a change to `docs/contracts/**`, `contract.yaml`, `codes.yaml`, the kernel or another service | `/raise-cr <svc> <reason>` drafts `docs/changes/CR-<PREFIX>-<n>.md` from `docs/global/templates/CR-template.md`. The developer takes it through `docs/global/CHANGE-PROCESS.md`. The WP waits or continues around it |
| SPEC is ambiguous or silent | Use the §13 provisional value if there is one and record it in PROGRESS.md. Otherwise the agent lists the question and the **developer** escalates to the service owner. No guessing |
| The same fix fails twice | `/fix-gate` stops by design. Start a fresh session with the error and a narrower instruction |
| A golden vector or test "looks wrong" | Never edit it. Raise it with the owner; a wrong vector is a CR against the producing pack |

## 6. PR review checklist (code owner)

**Scope**
- [ ] The branch is `<svc>/wp-<n>-<slug>`.
- [ ] Only `services/<svc>/**` changed.
- [ ] Nothing under `docs/contracts/` changed.
- [ ] Golden vectors are byte-identical.

**Tests**
- [ ] Every binding test name from the WP acceptance and SPEC §11 exists.
- [ ] Each binding test asserts what SPEC says, not something weaker.
- [ ] Failure, duplicate and concurrency paths are tested (≥ 100 threads where SPEC asks).
- [ ] No `@Disabled` tests.
- [ ] No coverage or ArchUnit exclusions.
- [ ] No leftover stub responses or TODOs.

**Code**
- [ ] K9 layering is respected.
- [ ] Money is `long` poisha.
- [ ] The outbox row is written in the same DB transaction as the state change.
- [ ] State updates are conditional.
- [ ] No PII in logs.

**Bookkeeping**
- [ ] PR shows gate output for `./gradlew clean check`, `contracts.sh check` and `make verify`, all green.
- [ ] `docs/PROGRESS.md` row added.
- [ ] Every §13 provisional value used is listed.
- [ ] `service` and `entity` packages read by a human (SPEC §12 asks for this explicitly).
- [ ] The "Reviewer focus" items from the PR text have been inspected.

## 7. Anti-patterns

- Several WPs in one session, or "implement the whole service".
- Skipping plan review, or approving a plan without the binding test list.
- Letting the agent open another service's `src/` "for reference". Use `consumed/` snapshots only.
- Asking the agent to "fix the test" when SPEC and code disagree. Ask it to fix the code to match SPEC.
- "Improving" pricing evaluators, golden vectors, txnRef formats or problem codes.
- Hand-editing generated code "just this once". The next agent session won't know why.
- Reviewing in the same session that wrote the code. The model defends its own choices.
- Letting the agent push, merge, or approve its own PR.

## 8. Maintaining the commands

The Claude Code skills in `.claude/skills/*/SKILL.md` are the source. Cursor commands are generated from them. After editing a skill, run from `bitspay-core/`:

```bash
for d in .claude/skills/*/; do n=$(basename $d); { echo "<!-- Generated from .claude/skills/$n/SKILL.md — edit that file, then re-run the sync loop in docs/AI-IMPLEMENTATION-GUIDE.md §8. -->"; awk 'BEGIN{f=0} /^---$/{f++; next} f>=2' $d/SKILL.md | sed 's/`\$ARGUMENTS`/the text typed after this command/'; } > .cursor/commands/$n.md; done
```

| Command | Purpose | Edits files? |
|---|---|---|
| `/start-wp <svc> <WP-n>` | Read the spec slice and produce a plan | No |
| `/implement-wp <svc> <WP-n>` | Test-first implementation until `./gradlew check` is green | Yes (service only) |
| `/review-wp <svc> <WP-n>` | Adversarial review in a fresh context; READY / NOT READY | No |
| `/fix-gate <svc> [gate]` | Root-cause a red gate; refuses to weaken tests | Yes (service only) |
| `/finish-wp <svc> <WP-n>` | Gates, PROGRESS.md, commit, PR description; never merges | Yes (PROGRESS.md + commit) |
| `/raise-cr <svc> <reason>` | Stop and draft a change request | Yes (`docs/changes/` only) |

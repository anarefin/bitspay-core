# Implementing a service — step by step

The checklist a developer follows to build **their** service (`services/<svc>/`) with Claude Code or Cursor, without the agent touching any other service. Run every command from the `bitspay-core/` root unless a step says otherwise. For the reasoning behind each step, see [AI-IMPLEMENTATION-GUIDE.md](AI-IMPLEMENTATION-GUIDE.md).

The examples use `wallet-service`, module `wallet`, `WP-3`. Replace them with your own.

## 1. Once per machine

1. Install JDK 25, Docker (about 10 GB of memory), `make` and Python 3 with PyYAML.
2. Build and start the stack once:
   ```bash
   make build && make up && make welcome
   ```
3. Install the repo git hooks. This adds the pre-commit check that enforces the scope lock:
   ```bash
   make hooks
   ```
   `make lock` also runs this. Check it with `git config core.hooksPath`, which should print `scripts/git-hooks`.

## 2. Once per service

1. Read `services/<svc>/CLAUDE.md` in full. It lists the binding rules for your service.
2. Open `services/<svc>/docs/SPEC.md` §10 (work packages) and `services/<svc>/docs/PROGRESS.md`.
3. Pick the next WP. All of its "Depends on" WPs must be `done` in PROGRESS.md. If the WP is the Compose-stack integration WP, check the wave table in [the guide §3](AI-IMPLEMENTATION-GUIDE.md#3-what-to-build-in-what-order) first.

## 3. Start of every work package

1. Create a branch. Any name works:
   ```bash
   git switch mvp-main && git pull
   git switch -c kyc-tiers
   ```
2. **Lock the scope to your service.** Do this before the agent starts:
   ```bash
   make lock svc=wallet-service
   make scope        # → Scope locked to wallet-service
   ```
3. Start the agent:
   - **Claude Code:** `cd services/wallet-service && claude`. The hook is set in `services/<svc>/.claude/settings.json`, so it is also active from the repo root.
   - **Cursor:** open the `bitspay-core/` folder. Hooks come from `.cursor/hooks.json`. Check they are enabled under *Settings → Hooks*.

## 4. The WP loop

| # | Step | Claude Code | Cursor |
|---|---|---|---|
| 1 | Plan | Plan mode (Shift+Tab) → `/start-wp wallet-service WP-3` | Plan mode → `/start-wp wallet-service WP-3` |
| 2 | **You** review the plan | Check against [guide §4.1](AI-IMPLEMENTATION-GUIDE.md#41-what-to-check-in-a-plan-step-3), then `approve` or correct | same |
| 3 | Implement (TDD) | Leave plan mode → `/implement-wp wallet-service WP-3` | Agent mode → same command |
| 4 | Red gate | `/fix-gate wallet-service <gate or test>` | same |
| 5 | Independent review | `/clear` → `/review-wp wallet-service WP-3` | New chat → same command |
| 6 | Fix findings | "Fix these findings, test-first, then re-run `./gradlew check`." + paste the BLOCKER/MAJOR rows | same |
| 7 | Finish | `/finish-wp wallet-service WP-3` (gates, PROGRESS.md, commit, PR text) | same |

`/start-wp` stops at once if the scope isn't locked to the service you named.

## 5. When the scope guard blocks something

While the lock is set, the agent **may** change:
- anything under `services/<your-svc>/`;
- root files such as `Makefile`, `compose.yaml`, `docs/`, `scripts/` and `docker/`.

It **may not** change anything under another `services/<other>/`, including through the `.contracts-view/` symlinks. Reading other files is still possible, but your service's CLAUDE.md forbids reading another service's code. Use `docs/contracts/consumed/` instead.

| You see | Meaning | Do |
|---|---|---|
| `Scope is locked to wallet-service. These paths belong to another service…` on an edit | The agent tried to edit another service | Tell the agent: "Stay in `services/wallet-service/`." If the other service really must change, run `/raise-cr wallet-service <reason>` |
| Same message on a shell command | The command names another service and is not read-only (`>`, `rm`, `sed -i`, `cd ../x && ./gradlew …`) | As above. Read-only commands (`cat`, `ls`, `grep`, `git diff/log/show`) are allowed |
| Cursor: `The edit was reverted.` | An edit got past the pre-edit hook and was undone after the fact | As above |
| `pre-commit: Scope is locked…` on `git commit` | A staged file belongs to another service, for example after `scripts/contracts.sh snapshot all` | `git restore --staged <path>`. Snapshot updates for other services go in their own branch, from that service's lock |

Rules:
- **Never run `make unlock` just to get past the guard.** A block means the change belongs to someone else's service or to a CR.
- **Never let the agent touch `.agent-scope`.** Lock and unlock are commands only you run.
- **Working on two services at once:** use one git worktree per service. Each checkout has its own lock:
  ```bash
  git worktree add ../bitspay-core-ledger -b ledger-work
  cd ../bitspay-core-ledger && make lock svc=ledger-service
  ```

## 6. Finish

1. All three gates must be green. `/finish-wp` runs them, and you can re-run them yourself:
   ```bash
   (cd services/wallet-service && ./gradlew clean check)
   scripts/contracts.sh check wallet-service
   make verify
   ```
2. Push and open the PR with the description `/finish-wp` printed:
   ```bash
   git push -u origin HEAD
   ```
3. Release the lock, or move it to your next service:
   ```bash
   make unlock       # or: make lock svc=<next-service>
   ```
4. The code owner reviews with the [guide §6 checklist](AI-IMPLEMENTATION-GUIDE.md#6-pr-review-checklist-code-owner). Agents never merge.

## 7. Quick reference

| Command | What it does |
|---|---|
| `make lock svc=<svc>` | Lock agents to one service; installs git hooks |
| `make scope` | Show the current lock |
| `make unlock` | Remove the lock (agents may change any service) |
| `make hooks` | Install git hooks (`core.hooksPath=scripts/git-hooks`) |
| `scripts/scope.sh check <path>…` | Exit 2 if a path is outside the locked service |
| `./gradlew check` (in the service) · `scripts/contracts.sh check <svc>` · `make verify` | The three gates |

## How the guard works (for maintainers)

- `.agent-scope` is gitignored and holds the locked service name. With no lock, every guard allows everything.
- All the rules live in `scripts/scope_check.py`. It resolves symlinks, so `.contracts-view/services/NN-<svc>` counts as `<svc>`. These callers use it:
  - **Claude Code:** a `PreToolUse` hook for Edit/Write/NotebookEdit/Bash in `.claude/settings.json` and in every `services/<svc>/.claude/settings.json`. Claude Code reads project settings only from the folder it was started in, so each service needs its own copy. Exit code 2 blocks the tool.
  - **Cursor:** `.cursor/hooks.json`. `preToolUse` and `beforeShellExecution` deny the action; `afterFileEdit` reverts an out-of-scope edit as a backstop.
  - **Git:** `scripts/git-hooks/pre-commit` checks the staged files.
- Limits: the guard protects against agent mistakes, not determined humans (`make unlock`, `git commit --no-verify`). The shell check is a heuristic, so the pre-commit hook is the final local gate.
- `Service Specs v6/create-skeleton.sh --force` may overwrite `services/<svc>/.claude/settings.json`. Restore them from git afterwards, as with the other hand-maintained root files.

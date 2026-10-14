---
name: finish-wp
description: Finish one Bits Pay work package — run all gates, update PROGRESS.md, commit, print the PR description. Never merges.
argument-hint: <service> <WP-n>
disable-model-invocation: true
---
# Finish a work package

Input: `$ARGUMENTS` = `<service> <WP-n>`. SVC is the service, WP the work package.

Precondition: `/review-wp` said `Verdict: READY`, or every BLOCKER and MAJOR finding has been fixed.

1. Branch: `git branch --show-current` must be `SVC/wp-<n>-<slug>` or `SVC/<module>/wp-<n>-<slug>` (kernel K9). If it is `main`, stop and ask.
2. Run every gate and show the last lines of each:
   - `cd services/SVC && ./gradlew clean check`
   - `../../scripts/contracts.sh check SVC`
   - from the `bitspay-core/` root: `make verify`
   If any is red, stop and follow `/fix-gate`.
3. `git status`: only `services/SVC/**` may have changed. Otherwise stop and list the extra paths.
4. Update `services/SVC/docs/PROGRESS.md`: add the row `| WP-n <title> | done | <tests added>, deviations, §13 provisional values used |`.
5. Commit with Conventional Commits and the service as scope: `feat(SVC): WP-n <title>`, body listing the main changes and the acceptance tests. Do not push unless the developer asks. Never merge.
6. Print the PR description:
   - **Summary** — SPEC §10 WP-n and the refs it implements.
   - **Acceptance tests** — binding names, all green.
   - **Gates** — `check`, contracts, `make verify` results.
   - **Deviations / §13 values / follow-ups.**
   - **Reviewer focus** — the three riskiest places in the diff (`file:line`) and why.

<!-- Generated from .claude/skills/review-wp/SKILL.md — edit that file, then re-run the sync loop in docs/AI-IMPLEMENTATION-GUIDE.md §8. -->
# Review a work package (fresh context, read-only)

Input: the text typed after this command = `<service> <WP-n>`. SVC is the service, WP the work package.

Run this in a NEW session or chat, not the one that wrote the code. Do not edit any file — produce findings only.

1. Collect the change: `git diff main...HEAD -- services/SVC`, plus `git status` and `git diff -- services/SVC` for uncommitted work.
2. Read `services/SVC/CLAUDE.md`, the SPEC §10 entry for WP, its §11 rows, §12, the contracts it touches and the relevant kernel rules in `docs/global/GLOBAL-CONVENTIONS.md`.
3. Check each item and report every failure:
   - Every acceptance and §11 test name for WP exists and asserts what SPEC says, not a weaker version.
   - Behaviour matches SPEC business rules (BR-…) and `docs/contracts/provided/*` exactly: paths, status codes, problem `code` and extension members, event envelope and key.
   - Outgoing calls and parsed events match `docs/contracts/consumed/*`.
   - Kernel: K9 layering, money as `long`, idempotency, outbox row in the same DB transaction, conditional state updates, schema isolation, no PII in logs.
   - Nothing outside `services/SVC/` changed; nothing under `docs/contracts/` changed; golden vectors untouched.
   - Failure, concurrency and duplicate-delivery paths that SPEC requires are tested, not only the happy path.
   - No leftover stub responses, TODOs, dead code, `@Disabled` tests or coverage/ArchUnit exclusions.
4. Output a table — severity (BLOCKER / MAJOR / MINOR), `file:line`, finding, SPEC or contract reference, suggested fix — then one line: `Verdict: READY` or `Verdict: NOT READY`.

Skip style points the compiler or ArchUnit already enforce.

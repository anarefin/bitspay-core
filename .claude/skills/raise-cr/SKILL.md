---
name: raise-cr
description: Stop implementation and draft a Bits Pay change request when work needs a contract, kernel or cross-service change.
argument-hint: <service> <short reason>
disable-model-invocation: true
---
# Raise a change request

Input: `$ARGUMENTS` = `<service>` plus a short reason. SVC is the service. Use this when the work needs a change to anything under `docs/contracts/`, `contract.yaml`, `codes.yaml`, the kernel, or another service.

1. Stop implementation. Do not edit any contract file.
2. Read `docs/global/CHANGE-PROCESS.md`. Classify the change as kind A–E, with one sentence of justification.
3. Find the next free number in `services/SVC/docs/changes/`. Use the CR prefix named in `services/SVC/CLAUDE.md` (e.g. `CR-TX`, `CR-WALLET`, `CR-LED`).
4. Create `services/SVC/docs/changes/CR-<PREFIX>-<n>.md` from `docs/global/templates/CR-template.md`. Fill §1 Motivation (SPEC/SRS refs, which WP is blocked), §2 Change before → after with exact fields and JSON, §3 Artefacts touched in the impact syntax, §4 Proposed versions. Leave §5–§7 empty and State = Draft.
5. Tell the developer: the CR path, its kind, the consumers likely impacted (from `docs/global/DEPENDENCY-INDEX.md`), and that the next step is analysis and approval per CHANGE-PROCESS.md — not more code.

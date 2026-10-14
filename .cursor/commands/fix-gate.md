<!-- Generated from .claude/skills/fix-gate/SKILL.md — edit that file, then re-run the sync loop in docs/AI-IMPLEMENTATION-GUIDE.md §8. -->
# Fix a failing gate

Input: the text typed after this command = `<service>` and optionally the failing gate (`check`, `integrationTest`, `contracts`, `verify`) or test name. SVC is the service. The developer may paste output below.

1. Reproduce. From `services/SVC/`: `./gradlew check`, `./gradlew integrationTest --tests '<X>'` or `../../scripts/contracts.sh check SVC`; from the `bitspay-core/` root: `make verify`. Read the first real error, not the last line. Reports: `build/reports/tests/`, `build/reports/jacoco/`.
2. State the root cause in one or two sentences with evidence (`file:line`, log line). Classify: production bug, test bug versus SPEC, environment (Docker, ports, Testcontainers), coverage gap, or contract drift.
3. Fix the cause, not the symptom. Forbidden: deleting or `@Disabled`-ing tests, loosening assertions, lowering the JaCoCo threshold, excluding classes from coverage or ArchUnit, editing `docs/contracts/**`. If the only fix is one of those, stop and explain.
4. Re-run the gate and every test you touched. Report the result with the last lines of output.

If the same fix has failed twice, stop and summarise what you tried. Do not loop.

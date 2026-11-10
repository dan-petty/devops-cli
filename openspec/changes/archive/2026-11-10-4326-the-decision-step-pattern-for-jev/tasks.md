# Tasks

## 1. Write the record

Reads: `docs/adr/0018-a-sandboxed-read-only-run-tool-for-the-planner.md`, `src/devops_cli/ai/jev.py`, `src/devops_cli/ai/jev_ask.py`, `src/devops_cli/roadmap/failure.py`. Changes: `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md` (new), `openspec/specs/decision-steps/spec.md` (new, by archive).

- [x] 1.1 Add the ADR with the status, the context of the three trials, the seven rules, the ranked candidates, the list of what is not suited, the two pilots with their bars, the considered options and the consequences
  - Verification: `$ uv run devops ci docs`
- [x] 1.2 Add the capability spec `decision-steps` with the requirements for the closed question set, the evidence, the fitted thresholds, the bands, the shadow log and the fail-open rule
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pilot 1, the verify screen, is issue #4282.
- Pilot 2, the failure-class tail, waits for the shared parts of pilot 1. A person files it after pilot 1 is measured.

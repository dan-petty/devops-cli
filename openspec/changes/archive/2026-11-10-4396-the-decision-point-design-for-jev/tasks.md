# Tasks

## 1. Design record

Reads: `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`, `src/devops_cli/roadmap/decision_step.py`, `src/devops_cli/config/settings.py`. Changes: `docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md` (new), `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`.

- [x] 1.1 Write ADR 0020 and amend the three places of ADR 0019
  - Verification: `$ uv run devops ci docs`

## 2. Specs

Changes: `openspec/changes/4396-the-decision-point-design-for-jev/specs/decision-workflows/spec.md` (new), `openspec/changes/4396-the-decision-point-design-for-jev/specs/decision-steps/spec.md`.

- [x] 2.1 Add the capability `decision-workflows` and modify two requirements of `decision-steps`
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- The registry, the settings and the migration of the verify screen are the next item of the design.
- `stage.explore_stop` in shadow is the item after it.
- Pending a person: review the design record.

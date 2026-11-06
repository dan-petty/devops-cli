# Tasks

## 1. The Plan Check job in the title workflow (other)

- [x] 1.1 Write the invariant tests of the job in `tests/invariants/test_workflow_contracts.py`: needs and `always()`, permissions, the condition for a plan of the Service and for other pull requests, the login of the bot, the title of the stage job, and the steps.
  Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Add the job `plan-check` to `.github/workflows/pr-title.yml`.
  Verification: `uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Documents of the job (other)

- [x] 2.1 Describe the job in `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: make `Plan Check` a required check in the ruleset of `main` (ADR 0014) after the plan reader gives no false alarm.

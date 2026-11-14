# Tasks

## 1. Behavior

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/ai/tasks/roadmap_intake_system.md`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/ai/tasks/roadmap_intake_system.md`, `tests/roadmap/intake/test_roadmap_intake_model_reply.py`, `tests/roadmap/intake/test_roadmap_intake_checks.py`, `tests/roadmap/intake/__snapshots__/test_roadmap_intake_duplicates.ambr`.

- [ ] 1.1 Add failing test asserting P0-Critical in the reply schema and intake priority validation
  - Verification: `$ uv run pytest -n 0 tests/roadmap/intake/test_roadmap_intake_model_reply.py tests/roadmap/intake/test_roadmap_intake_checks.py`
- [ ] 1.2 Include P0-Critical in model priorities, update Jev priority criteria, and remove priority capping in intake
  - Verification: `$ uv run pytest -n 0 tests/roadmap/intake/test_roadmap_intake_model_reply.py tests/roadmap/intake/test_roadmap_intake_checks.py`
- [ ] 1.3 Update intake system prompt with P0 and P1 criteria and refresh snapshot
  - Verification: `$ uv run pytest -n 0 tests/roadmap/intake/test_roadmap_intake_duplicates.py`

## 2. Documents

Kind: documents. Reads: `docs/roadmap/intake.md`. Changes: `docs/roadmap/intake.md`.

- [ ] 2.1 Update intake documentation with P0 and P1 criteria and updated priority options
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_roadmap_workflow_doc.py`

## Workflow follow-up
Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

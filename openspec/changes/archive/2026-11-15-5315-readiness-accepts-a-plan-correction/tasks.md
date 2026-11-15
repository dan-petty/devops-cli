# Tasks

## 1. Accept a changed plan file

Reads: `src/devops_cli/roadmap/grounding.py`, `tests/roadmap/test_grounding.py`.

Changes: `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_grounding.py`.

- [x] 1.1 Write the correction and removal cases and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/test_grounding.py`
- [x] 1.2 Widen the statuses and correct the message.
  - Verification: `$ uv run devops ci test tests/roadmap/test_grounding.py`

## Workflow follow-up

- Pending a person: none.

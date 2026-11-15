# Tasks

## 1. Compare the code spans with the declared phrases

Reads: `src/devops_cli/roadmap/plan_check.py`, `openspec/changes/archive/2026-11-07-3304-add-a-set-count-to-every/tasks.md`.

Changes: `src/devops_cli/roadmap/plan_phrases.py`, `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_plan_phrases.py`, `docs/roadmap/plan-check.md`.

- [x] 1.1 Write the five cases and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_phrases.py`
- [x] 1.2 Add the module, the message and the call in `folder_problems`, and name the check in the page.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_phrases.py tests/roadmap/test_roadmap_plan_check.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

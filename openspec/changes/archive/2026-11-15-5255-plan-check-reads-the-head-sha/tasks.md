# Tasks

## 1. Read the named head

Reads: `src/devops_cli/roadmap/plan_check.py`, `tests/roadmap/test_roadmap_plan_check.py`.

Changes: `src/devops_cli/roadmap/plan_check.py`, `tests/roadmap/test_roadmap_plan_check.py`.

- [x] 1.1 Write the moved-ref test and watch it fail.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py`
- [x] 1.2 Fetch the head SHA and read it in place of `FETCH_HEAD`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

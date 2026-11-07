# Tasks

## 1. The reader reports a criterion that the model refuses

Reads: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage_criteria.py`, `tests/roadmap/test_roadmap_plan_read.py`. Changes: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/lang/en/messages.py`, `docs/roadmap/plan-check.md`, `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 1.1 Add failing tests: `read_change` raises `PlanReadError` for `tasks.md` on a criterion of group 0, plan-check reports it as a `read` problem, and plan-recheck refuses the folder at the gate `read`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` fails on the base
- [x] 1.2 Turn the `ValidationError` of `StageCriterion` in `_criteria` into a `PlanReadError` for `tasks.md`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_read.py` passes
- [x] 1.3 List the criterion among the read problems in `docs/roadmap/plan-check.md`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

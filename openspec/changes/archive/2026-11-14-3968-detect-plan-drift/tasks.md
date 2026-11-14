# Tasks

## 1. The drift row

- [x] 1.1 Add `src/devops_cli/roadmap/stage/plan_drift.py`: the plan filter, the default-branch check, the label and the one comment.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py`
- [x] 1.2 Register the row before `stage_ready` and add its interval to `src/devops_cli/config/defaults.py`.
  Verification: `uv run devops ci test tests/roadmap/test_roadmap_run_due_table.py tests/roadmap/stage/test_roadmap_stage_ready.py`

## 2. The tests

- [x] 2.1 Cover the comment, the label addition, the label removal and the delivery exclusion.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py -k "row or comment"`
- [x] 2.2 Cover a path that the default branch moved.
  Verification: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_drift.py -k moved`
- [x] 2.3 Run the quality gate and the roadmap tests.
  Verification: `uv run devops ci --check --only lint,format,typecheck && uv run devops ci test tests/roadmap`

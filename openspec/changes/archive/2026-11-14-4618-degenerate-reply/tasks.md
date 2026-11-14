# Tasks

## 1. One bullet for the degenerate reply

Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: the same file and `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`.

- [x] 1.1 Set `_stopped_by_checks` in `_stop_degenerate`.
- [x] 1.2 Add the round test.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py` passes

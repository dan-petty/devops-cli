# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for rejected-plan clear, manual return clear, `stage_ready` finished-job handling, and `fix_plan` finished-job handling (`tests/roadmap/stage/test_roadmap_stage_rejected.py`, `tests/roadmap/test_roadmap_return.py`, `tests/roadmap/stage/test_roadmap_stage_ready.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py tests/roadmap/test_roadmap_return.py tests/roadmap/stage/test_roadmap_stage_ready.py tests/roadmap/steps/test_roadmap_fix_plan.py`
- [x] 1.2 Add `src/devops_cli/roadmap/implement/record_clear.py`, clear implement run keys in `_reject_plan` and `apply_return` (excluding `implement_report.return_to_new`), and switch `stage_ready` and `fix_plan` to `job_holds`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_rejected.py tests/roadmap/test_roadmap_return.py tests/roadmap/stage/test_roadmap_stage_ready.py tests/roadmap/steps/test_roadmap_fix_plan.py`

## 2. Documents

- [x] 2.1 Run OpenSpec and static quality gates across all modified files
  - Verification: `$ uv run devops openspec check`

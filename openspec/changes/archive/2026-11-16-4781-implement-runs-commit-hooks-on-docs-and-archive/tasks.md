# Tasks

## 1. Behavior

- [x] 1.1 Add unit tests for `_commit_if_changed` running commit hooks
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_job_hooks.py`
- [x] 1.2 Update `_commit_if_changed` in `src/devops_cli/roadmap/implement/implement_run.py` to call `commit_stage`
  - Verification: `$ uv run pytest tests/roadmap/implement/test_roadmap_implement_job_hooks.py`

## 2. OpenSpec

- [x] 2.1 Update `openspec/specs/roadmap-implement-job/pull-request/spec.md` with commit hook requirements
  - Verification: `$ uv run devops openspec check`

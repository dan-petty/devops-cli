# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for unknown-label default refusal, project-namespace rows with `name`, safe-label rows, and shipped `catalog.yaml` `rows` facts (`tests/roadmap/project_review/test_review_dispatch.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py`
- [x] 1.2 Replace `_WORKLOAD_LABELS` in `src/devops_cli/roadmap/project_review/dispatch.py` with `_SAFE_ROW_LABELS` default refusal
  - Verification: `$ uv run devops ci test tests/roadmap/project_review/test_review_dispatch.py`

## 2. Documents

- [x] 2.1 Update the safe-label rule documentation in `dispatch.py`, `src/devops_cli/roadmap/project_review/catalog.yaml`, and `docs/ROADMAP_WORKFLOW.md` and run OpenSpec check
  - Verification: `$ uv run devops openspec check`

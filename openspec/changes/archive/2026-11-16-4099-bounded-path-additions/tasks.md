# Tasks

## 1. Implement bounded path additions in plan requests

Reads: `src/devops_cli/roadmap/implement/implement_amend.py`. Changes: `src/devops_cli/roadmap/implement/implement_amend.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`.

- [x] 1.1 Write tests for parsing and judging `add_path` requests in `tests/roadmap/implement/test_roadmap_implement_amend.py`, and verify that `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_amend.py` fails on the base
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_amend.py`
- [x] 1.2 Add `add_path` kind and `header` field to `PlanRequest` and implement `_judge_add_path` in `src/devops_cli/roadmap/implement/implement_amend.py`, and verify that `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_amend.py` passes
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_amend.py`

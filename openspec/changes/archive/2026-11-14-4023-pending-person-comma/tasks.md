# Tasks

## 1. Resolve a pending-person criterion

Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`. Changes: the same file and `tests/roadmap/stage/test_roadmap_stage_criteria.py`.

- [x] 1.1 Add `_resolved` and use it in `criterion_problems`.
- [x] 1.2 Add the four tests.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

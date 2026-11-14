# Tasks

## 1. Drop a cancelled criterion

Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`. Changes: the same file and `tests/roadmap/stage/test_roadmap_stage_criteria.py`.

- [ ] 1.1 Omit an item whose text starts and ends with `~~`.
- [ ] 1.2 Add the four tests.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py` passes

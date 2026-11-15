# Tasks

## 1. Behavior

- [x] 1.1 Write tests for final push rebase and conflict
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 1.2 Fetch and rebase in `_push` before publishing or pushing with lease
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`

## 2. Documents

- [x] 2.1 Update specifications and documentation
  - Verification: `$ uv run devops ci --check --only docs,openspec`

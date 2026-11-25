# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for zero `store.item` reads during refine and dependency checks
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_blocker_listing.py`
- [x] 1.2 Update `open_issue_dependencies` to require `open_numbers` and avoid `store.item`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py`
- [x] 1.3 Update refine `_open_blockers` and `_open_dependencies` to use `open_numbers`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_blocked.py`
- [x] 1.4 Update stage and implement callers to pass `open_numbers`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/ tests/roadmap/implement/`

## 2. Documents

- [x] 2.1 Update delta spec for roadmap-dependency-cycle
  - Verification: `$ uv run devops openspec check`

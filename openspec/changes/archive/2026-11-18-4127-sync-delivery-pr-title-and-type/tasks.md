# Tasks

## 1. Plan commit type and title derivation tests

- [x] 1.1 Write failing unit tests for Conventional Commit type derivation and proposal summary extraction
  - Verification: `$ uv run pytest -n 0 tests/roadmap/implement/test_roadmap_implement_title_sync.py`

## 2. Implementation

- [x] 2.1 Implement `plan_commit_type` and proposal summary extraction helpers
  - Verification: `$ uv run pytest -n 0 tests/roadmap/implement/test_roadmap_implement_title_sync.py`
- [x] 2.2 Wire title and type derivation in `Job._delivery_title` and remove stale type labels in `Job._delivery_metadata`
  - Verification: `$ uv run pytest -n 0 tests/roadmap/implement/test_roadmap_implement_job.py`

## 3. Verification

- [x] 3.1 Run quality gates and pre-commit checks
  - Verification: `$ uv run devops ci --check --only lint,format,typecheck`

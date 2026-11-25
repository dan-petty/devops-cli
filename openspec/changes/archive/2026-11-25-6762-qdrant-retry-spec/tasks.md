# Tasks

## 1. Tests

- [x] 1.1 Write failing tests in `tests/openspec/test_qdrant_retry_spec.py`
  - Verification: `$ uv run pytest tests/openspec/test_qdrant_retry_spec.py`

## 2. Specs

- [x] 2.1 Remove `qdrant-retry-wait-uses-clock-seam` from `openspec/specs/rag-lookup-pause/spec.md` and add the corrected requirement to `openspec/specs/qdrant-request-retry/spec.md`
  - Verification: `$ uv run pytest tests/openspec/test_qdrant_retry_spec.py && uv run devops openspec check`

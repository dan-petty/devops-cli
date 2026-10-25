# Tasks

## 1. Implementation

- [x] 1.1 Write the failing test `test_transient_lookup_failure_is_not_cached_and_empty_lookup_is_served_from_cache` in `tests/test_rag_investigator.py`. Verify with `uv run devops ci test tests/test_rag_investigator.py` and verify failure against base with `uv run devops ci fail-to-pass --base origin/main`.
- [x] 1.2 Update `investigate_rag_context` in `src/devops_cli/ai/rag/investigator.py` to cache in `_INVESTIGATION_CACHE` only when `ctx is not None`. Verify with `uv run devops ci test tests/test_rag_investigator.py`.
- [x] 1.3 Verify static checks and full suite with `uv run devops ci`.

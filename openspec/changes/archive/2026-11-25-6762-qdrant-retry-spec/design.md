# Design

## Decisions
- Move `qdrant-retry-wait-uses-clock-seam` from `rag-lookup-pause` to `qdrant-request-retry`, since `qdrant-request-retry` owns Qdrant client retry behavior (`src/devops_cli/ai/rag/qdrant.py`).
- Describe the implemented retry loop: `_execute_with_retry` runs up to `DEFAULT_MAX_RETRIES` (`3`) attempts and calls `_record_retry(..., sleep=sleep)` with `clock_seam.sleep` by default, yielding two backoff waits (`0.5` and `1.0` seconds).
- Add `tests/openspec/test_qdrant_retry_spec.py` to enforce the capability placement, absence of `tenacity`, presence of `sleep` and clock seam wording, and two-wait backoff sequence (`0.5` and `1.0`, no `1.5`).

## Rejected alternatives
- Keep `qdrant-retry-wait-uses-clock-seam` in `rag-lookup-pause`: rejected because Qdrant client retries belong in `qdrant-request-retry`.
- Rewrite `_execute_with_retry` to use `tenacity`: rejected because the existing loop and injected `clock_seam.sleep` already meet retry telemetry and test-seam requirements.

# Tasks

## 1. A gateway or rate-limit answer gets a retry

Kind: behavior. Reads: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_qdrant_request_telemetry.py`. Changes: `src/devops_cli/ai/rag/qdrant.py`, `tests/support/fakes/qdrant.py`, `tests/ai/rag/test_qdrant_request_retry.py`.
Adds: `_RETRY_STATUSES`, `ServedQdrant.error_statuses`

- [x] 1.1 Add the field `error_statuses: list[int]` to `ServedQdrant` in `tests/support/fakes/qdrant.py`: each of the next requests takes the first status of the list and gets that status with an HTML body, as a proxy in front of Qdrant answers. Write the failing test `test_a_gateway_or_rate_limit_answer_gets_a_retry` in `tests/ai/rag/test_qdrant_request_retry.py`, parametrized with 429, 502, 503 and 504. It sets up the collection `devops_docs`, sets the status, upserts one point through `upsert_points`, and asserts the count 1, the waits `[0.5]` of the `clock` fixture and two upsert requests. The cases 429, 502 and 503 fail on the base
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_retry.py` fails on the base
- [x] 1.2 Write the test `test_another_error_status_ends_the_operation_at_once` in the same file, parametrized with 400, 401, 403, 404, 408 and 500. It asserts that `upsert_points` raises `QdrantClientError` with `Unexpected Response: <status>`, no wait and one upsert request. The case 408 fails on the base
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_retry.py` fails on the base
- [x] 1.3 In `src/devops_cli/ai/rag/qdrant.py`, add the module-level `_RETRY_STATUSES: Final[frozenset[HTTPStatus]]` with 429, 502, 503 and 504, and make `_is_transient_qdrant_error` return `exc.status_code in _RETRY_STATUSES` for an `UnexpectedResponse`, before the search for connection words. Change its docstring to state the rule
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_retry.py tests/ai/rag/test_qdrant_request_telemetry.py tests/ai/rag/test_rag_qdrant.py` passes

## 2. State the error answers of the loopback Qdrant server

Kind: other. Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [ ] 2.1 In the Qdrant line of `docs/TESTING.md`, state that `serving_qdrant` can answer the next requests with an error status, and that a test of the retry of a gateway answer uses it
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

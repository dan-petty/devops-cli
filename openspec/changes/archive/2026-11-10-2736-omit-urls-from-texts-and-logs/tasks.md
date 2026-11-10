# Tasks

## 1. Ollama and validation error text

- [x] 1.1 Write the failing test that an Ollama URL with no host names no URL in its error.
  - Verification: `$ uv run devops ci test tests/ai/models/test_pydantic_ai_ollama.py`
- [x] 1.2 Write the failing test that a service URL with no hostname names no URL in its error.
  - Verification: `$ uv run devops ci test tests/core/test_validation.py`
- [x] 1.3 Remove the URL from both reason texts.
  - Verification: `$ uv run devops ci test tests/ai/models/test_pydantic_ai_ollama.py tests/core/test_validation.py`

## 2. Qdrant error text and log lines

- [x] 2.1 Write the failing test that an exception text with a URL becomes a label in the error and in the log line.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_server_label.py`
- [x] 2.2 Replace each URL in an exception text with its server label at every error message and log line of `QdrantClient`.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_server_label.py tests/ai/rag/test_rag_qdrant.py`

## 3. Label port range

- [x] 3.1 Write the failing test that a label gives `unknown` for a port outside 0 to 65535.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_server_label.py`
- [x] 3.2 Give `server_label` `unknown` for an out-of-range port.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_server_label.py`

## 4. Span and label agree on a malformed Service address

- [x] 4.1 Write the failing test that the upsert span of `k8s://devops` gives `server.address` `unknown` and does not raise.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_telemetry.py`
- [x] 4.2 Catch `ServiceAddressError` in `_server_span_attributes` and set `server.address` to `unknown`.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_qdrant_request_telemetry.py tests/ai/rag/test_qdrant_server_label.py`

## 5. Checks

- [x] 5.1 Run the static checks, the full test suite and the OpenSpec gate.
  - Verification: `$ uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).

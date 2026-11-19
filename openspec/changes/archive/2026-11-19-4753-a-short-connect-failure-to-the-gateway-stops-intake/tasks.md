# Tasks

## 1. Retry policy and transport updates

- [x] 1.1 Update connect retry policy with up to 10 attempts and deadline stop
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_retries.py`
- [x] 1.2 Implement pre-output stream reset retry and mid-stream failure handling
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_retries.py`

## 2. Error message formatting

- [x] 2.1 Update `_connection_error` to include error class, root cause, and host
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_error_reason.py`

## 3. Verification

- [x] 3.1 Add acceptance tests for all scenarios in `test_ai_client_retries.py`
  - Verification: `$ uv run devops ci test tests/ai/`

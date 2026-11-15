# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for async retry transport and stream reset retry
  - Verification: `$ uv run devops ci test tests/ai/retries/test_pydantic_ai_retries.py`
- [x] 1.2 Implement `create_async_retry_transport` in `src/devops_cli/ai/retries/__init__.py`
  - Verification: `$ uv run devops ci test tests/ai/retries/test_pydantic_ai_retries.py`
- [x] 1.3 Add `retries` to `async_http_client` and update `create_pydantic_ai_provider`
  - Verification: `$ uv run devops ci test tests/ai/retries/test_pydantic_ai_retries.py`
- [x] 1.4 Implement stream retry wrapper in `src/devops_cli/ai/pydantic_ai_bridge.py`
  - Verification: `$ uv run devops ci test tests/ai/retries/test_pydantic_ai_retries.py`

## 2. Documents

- [x] 2.1 Update documentation and verify OpenSpec gates
  - Verification: `$ uv run devops openspec check`

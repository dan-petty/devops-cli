# Tasks

## 1. Keep the status of a Claude reply after the retries

Kind: behavior. Reads: `src/devops_cli/ai/client/claude.py`, `src/devops_cli/ai/client/base.py`, `src/devops_cli/ai/retries/__init__.py`. Changes: `src/devops_cli/ai/client/claude.py`, `tests/ai/client/test_ai_client_error_reason.py`.

- [x] 1.1 In `tests/ai/client/test_ai_client_error_reason.py`, make `test_a_claude_reply_with_a_status_gives_the_status` send the chat call and the stream through the shared client of `_claude_client()`, with no plain client, and assert status 529, the reason `LLM_INFERENCE_ERROR, HTTP 529` and two tries. Add a test that a Claude reply 401 gives `AICredentialsError` with `HTTP 401`, and a `claude-refused` case of the provider test with no status. Run the file and see the 529 and 401 tests fail
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_error_reason.py`
- [x] 1.2 In the `anthropic.APIConnectionError` branch of `_map_anthropic_errors` in `src/devops_cli/ai/client/claude.py`, raise `self_obj._provider_http_error(exc.__cause__, failure)` when `exc.__cause__` is an `httpx2.HTTPStatusError`, before the connection error
  - Verification: `$ uv run devops ci test tests/ai/client/test_ai_client_error_reason.py tests/ai/client/test_claude_provider.py tests/ai/client/test_ai_streaming.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

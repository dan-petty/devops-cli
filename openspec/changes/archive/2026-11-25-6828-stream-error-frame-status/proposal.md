# Proposal: #6828

## Why
`LLMClient.chat_stream` through the gateway does not read the HTTP status from an SSE error frame after a keepalive comment because `_openai_compat_stream` catches only `openai.APIStatusError` and `openai.APIConnectionError`. A raw `openai.APIError` escapes without HTTP status, credentials, or spend-limit classification. Closes #6828.

## What Changes
- Catch `openai.APIError` in `_openai_compat_stream` (`src/devops_cli/ai/client/openai.py`) and delegate to `self._map_openai_error(exc)` so gateway SSE error frames map through `_frame_status` and `_status_error`.
- Pass `status=status` when building `AICredentialsError` in `credentials_error` (`src/devops_cli/ai/client/models.py`) so 401 and 403 credentials errors carry their HTTP status consistently.
- Add stream error-frame tests in `tests/ai/client/test_ai_streaming.py` covering HTTP 408 timeout frames, plain 403 credentials errors, 403 spent-key errors (`AIKeySpendLimitError`), and non-numeric error codes.

This change alters observable streaming error behavior in `LLMClient.chat_stream`, so it adds a requirement to `ai-client-error-reason`. It fits one pull request.

## Capabilities
- `ai-client-error-reason`: map SSE error frames in `LLMClient.chat_stream` through `_map_openai_error`.

## Impact
- Jobs using `LLMClient.chat_stream` (via gateway) receive structured `AIClientError` with HTTP `status` and `AIKeySpendLimitError` instead of unmapped `openai.APIError`.

## Feasibility
Confirmed against `origin/main` source (`src/devops_cli/ai/client/openai.py:103-137`, `:405-406`, and `:524`). `_map_openai_error` already handles `openai.APIError` via `_frame_status` and `_status_error`, while `_openai_compat_stream` catches only `(openai.APIStatusError, openai.APIConnectionError)`.

## Existing Tool Considered
Searches documented in #6828 (`2026-11-23`) found no library for mapping provider SSE error frames to project error classes. `_map_openai_error` already exists in `src/devops_cli/ai/client/openai.py`; reusing it in `_openai_compat_stream` changes one `except` tuple at negligible token cost and deletes no code.

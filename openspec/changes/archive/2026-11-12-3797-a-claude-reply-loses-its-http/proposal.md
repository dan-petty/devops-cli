# Proposal: #3797

## Why
A Claude call that gets an HTTP error reply loses the status of that reply (#3797). The Claude path sends through the shared client of `LLMClient`, which has the retry transport. After the last try, that transport raises `httpx2.HTTPStatusError` for a 4xx or 5xx reply. The Anthropic SDK wraps each error of its send in `anthropic.APIConnectionError`. `_map_anthropic_errors` in `src/devops_cli/ai/client/claude.py` then builds the "Cannot connect to Claude API" error with no status. Thus a reply 529 gives the reason `LLM_INFERENCE_ERROR` and not `LLM_INFERENCE_ERROR, HTTP 529`, and a reply 401 does not give the credentials error.

## What Changes
- `_map_anthropic_errors` reads the cause of an `anthropic.APIConnectionError`. When the cause is an `httpx2.HTTPStatusError`, it builds the error with `_provider_http_error`, as it does for an `httpx2.HTTPStatusError` that the SDK did not wrap. The error then has the status of the last reply, and a 401 or 403 gives `AICredentialsError`.
- An `APIConnectionError` with another cause keeps the connection error with no status.
- The Claude test of `tests/ai/client/test_ai_client_error_reason.py` uses the shared client with its retry transport, and not a plain client.

The change alters the error that a consumer reads, so it has a spec delta.

## Capabilities
- `ai-client-error-reason`: ADDED requirement for the status of a Claude reply after the retries of the shared client.

## Impact
- `src/devops_cli/ai/client/claude.py`: the `APIConnectionError` branch of `_map_anthropic_errors`.
- `tests/ai/client/test_ai_client_error_reason.py`: the Claude tests.
- A job log and a stop reason of a Claude call now name the HTTP status. The chat call and the stream use the same mapper.

The change fits one pull request.

## Feasibility
- The Anthropic SDK 1.12.1 (`anthropic/_base_client.py`, `SyncAPIClient._send_single_request`) catches each exception of `self._client.send` that is not an `AnthropicError` and runs `raise APIConnectionError(request=request) from err`. Thus the `__cause__` of the `APIConnectionError` is the exception of the transport.
- `create_retry_transport` in `src/devops_cli/ai/retries/__init__.py` gives `HTTPX2TenacityTransport` (pydantic-ai) a `validate_response` that calls `raise_for_status()` for a status of 400 or more, and `reraise=True`. After the last try, the transport raises that `httpx2.HTTPStatusError`.
- `_shared_client` in `src/devops_cli/ai/client/base.py` builds the client with `retries=self._max_attempts()`, so each Claude call that gets no `http_client` uses the retry transport.
- A copy of `test_a_claude_reply_with_a_status_gives_the_status` that uses the shared client and the `web` fake gave `(None, 'LLM_INFERENCE_ERROR')` on `origin/main`, not `(529, 'LLM_INFERENCE_ERROR, HTTP 529')`.

## Existing Tool Considered
No open tool covers this: the fix reads an exception that the code already gets, and it reuses `_provider_http_error` of `src/devops_cli/ai/client/base.py`. The alternatives check of the issue found no tool. The cost to build is about 3,000 tokens to change, test and keep the code, and about 30 minutes of elapsed time. The change deletes no internal code.

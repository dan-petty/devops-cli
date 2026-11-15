# Proposal: #5806

## Why
Agent runs on the async pydantic-ai path can fail when the reply stream receives a connection reset before the first chunk. The async HTTP client installs no retry transport, and reading the response body occurs outside the transport. This change adds an opt-in retry policy for the async client and a retry wrapper before the first chunk. Closes #5806.

## What Changes
- Add the `retries` parameter to `async_http_client` in `src/devops_cli/http/entry.py`.
- Implement `create_async_retry_transport` in `src/devops_cli/ai/retries/__init__.py`.
- Update `create_pydantic_ai_provider` in `src/devops_cli/ai/providers/__init__.py` to pass `retries=3`.
- Implement `StreamRetryModel` and `wrap_stream_retry_model` in `src/devops_cli/ai/pydantic_ai_bridge.py` to retry resets before the first chunk and reject retries after output.
- Keep the GitHub session client unchanged without retry transport.

## Capabilities
- `ai-agent-stream-retry`: Retry a pydantic-ai model stream on reset before the first chunk, with opt-in async retry transport.

## Impact
- Pydantic-AI agent runs recover from transient connection resets before output starts.
- GitHub session is unaffected.
- No rerun of side-effects occurs after stream output starts.

## Feasibility
- Verified with PydanticAI `AsyncHTTPX2TenacityTransport` and the existing sync retry transport pattern in `src/devops_cli/ai/retries/__init__.py`.
- Tested stream wrapper around pydantic-ai model stream execution.

## Existing Tool Considered
PydanticAI `AsyncHTTPX2TenacityTransport` covers transport-level connect retries but not a reset after the reply body starts. The change adds a stream wrapper before the first chunk and reuses `AsyncHTTPX2TenacityTransport` for the transport level.

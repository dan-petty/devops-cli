# Proposal

## Why

Issue #1427. The `openai` provider without `ai.api_base_url` sends chat completions and model listings to `https://api.openai.com/chat/completions` and `https://api.openai.com/models`. The OpenAI API serves those routes under `/v1`. Hand-written URL construction, payload builders, and response parsers cause this defect. The `openai` SDK defaults to `https://api.openai.com/v1` and accepts an `httpx2.Client` from the egress factory.

## What Changes

- Update `OpenAICompatProviderMixin` in `src/devops_cli/ai/client/openai.py` to route requests through `openai.OpenAI`.
- Configure the SDK client with the egress factory HTTP client, short timeouts, and `max_retries=0`.
- Let provider `openai` use the SDK default base URL (`https://api.openai.com/v1`), while `copilot` and `gateway` preserve their configured endpoints.
- Read gateway served-by headers from `with_raw_response` or stream response headers.
- Extract reasoning content from delta extra fields during chat completions and streaming.
- Delete `CONST_URL_OPENAI_API_BASE`, `_build_compat_payload`, `_parse_compat_response`, `_openai_compat_headers`, and `_openai_stream_frame`.
- Update `src/devops_cli/ai/rag/embeddings.py` to obtain default base URL from the SDK rather than a hand-written string.
- Add failing tests verifying unstreamed chat, streamed chat, and model listing reach `/v1` routes and use the egress client.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/client/streaming.py`, `src/devops_cli/ai/client/unified.py`, `src/devops_cli/ai/endpoints.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/config/constants.py`.
- Tests: `tests/test_ai_client_providers_and_embeddings.py`, `tests/test_ai_benchmark.py`, `tests/test_ai_streaming.py`, `tests/test_thinking_providers.py`.

## Feasibility

- Premise confirmed by running `LLMClient` against `route_client` on `origin/main`.
- Recorded requests confirmed that `openai` provider without `api_base_url` sent to `https://api.openai.com/chat/completions` and `https://api.openai.com/models` without `/v1`.
- Verified `openai.OpenAI` SDK version 3.26.1 initializes with `http_client=httpx2.Client()`.
- Verified `openai.OpenAI` sends to `https://api.openai.com/v1/chat/completions` by default.
- Verified stream reasoning extraction reads `reasoning_content` from `ChoiceDelta.model_extra`.

## Existing Tool Considered

The change adopts the installed `openai` Python SDK (version 3.26.1) instead of hand-written HTTP request assembly. The SDK manages routing, authentication headers, SSE frame decoding, and error typing. The egress factory client (`new_http_client`) remains the underlying transport.

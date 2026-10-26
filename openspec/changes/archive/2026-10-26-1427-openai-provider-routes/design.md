# Design

## Context

The `devops-cli` tool interacts with OpenAI-compatible APIs across three providers: `openai`, `copilot`, and `gateway`.
Previously, `OpenAICompatProviderMixin` built HTTP requests by hand. It appended `/chat/completions` directly to `CONST_URL_OPENAI_API_BASE` (`https://api.openai.com`), omitting the required `/v1` prefix.

## Architecture

`OpenAICompatProviderMixin` holds an `openai.OpenAI` SDK client instance.
The client configuration follows these rules:
1. `http_client`: Supplied from `self._shared_client()`, preserving connection pooling and SSRF egress filtering.
2. `base_url`: When `self._config.provider == "openai"` and `self._config.api_base_url` is unset, `base_url` is omitted (`None`). The SDK defaults to `https://api.openai.com/v1`. When `api_base_url` or another provider is set, `self._validate_base_url` supplies the endpoint.
3. `api_key`: Supplied from `self._api_key or "none"`.
4. `max_retries`: Set to 0 so the tenacity transport in the factory client handles retries without multiplication.
5. `timeout`: Configured from `self._request_timeout()`.

## Request Handling

### Unstreamed Chat (`_openai_compat_messages`)

- Execute request with `with_streaming_response.create(...)`.
- Read and cap response body bytes with `_read_limited_body` against `DEFAULT_AI_MAX_RESPONSE_BYTES`.
- Parse the response model via `response.parse()`.
- Extract response headers for gateway `x-served-by` attribution.
- Map reasoning text from message fields or `model_extra`.
- Map token usage and finish reason to `LLMResponse`.

### Streamed Chat (`_openai_compat_stream`)

- Execute request with `chat.completions.create(..., stream=True, stream_options={"include_usage": True})`.
- Read stream response headers for gateway metadata.
- Iterate over chunks and yield text or `<think>{reasoning}</think>` tags.
- Update `stream_usage`, `stream_model`, and `stream_finish_reason` ContextVars.
- Ensure stream closure in a `finally` block.

### Model Listing (`_openai_models`)

- Call `self._openai_client().models.list()`.
- Return model ID list from `listing.data`.

### Error Mapping

- Catch `openai.APIStatusError` and map HTTP 401/403 to `AICredentialsError` through `credentials_error`.
- Map other `openai.APIStatusError` to `AIClientError` with sanitized error messages.
- Catch `openai.APIConnectionError` and map to `AIClientError` via `self._connection_error(exc)`.

## Deletions

- Remove `CONST_URL_OPENAI_API_BASE` from `src/devops_cli/config/constants.py`.
- Remove `_build_compat_payload`, `_parse_compat_response`, `_openai_compat_headers` from `src/devops_cli/ai/client/openai.py`.
- Remove `_openai_stream_frame` from `src/devops_cli/ai/client/streaming.py`.

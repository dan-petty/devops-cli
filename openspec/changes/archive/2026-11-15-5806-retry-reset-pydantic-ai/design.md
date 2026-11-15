# Design

## Decisions

### Async retry transport
Use PydanticAI `AsyncHTTPX2TenacityTransport` with `create_retry_config` for the async HTTP transport retry layer. Wrap the effective transport in `AsyncExpiringConnectionTransport` to close expired connections across attempts. Add `retries: int | None = None` to `async_http_client` and `_build_async_client` in `src/devops_cli/http/entry.py`.

### Stream wrapper at the stream boundary
Wrap the model stream at the stream boundary using a model wrapper subclassing `WrapperModel`. When a reset occurs before the first chunk is emitted, retry the stream up to three attempts with backoff. When a reset occurs after the first chunk has been emitted, do not retry and raise `AIClientError` immediately. Do not retry HTTP 4xx responses.

### Opt-in provider configuration
Pass `retries=3` from `create_pydantic_ai_provider` in `src/devops_cli/ai/providers/__init__.py`. Keep the GitHub session client unchanged without `retries` to preserve its separate retry rules.

## Rejected alternatives

### Tenacity around the whole agent run
Rejected because retrying the whole agent run can repeat tool calls and side effects after output.

### Custom transport only
Rejected because the transport layer returns before the reply stream is consumed, so it cannot handle resets during the reply read.

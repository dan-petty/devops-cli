# Design

## Decisions
- The `APIConnectionError` branch of `_map_anthropic_errors` reads `__cause__` only. The SDK raises `APIConnectionError` directly `from` the exception of `httpx2.Client.send`, and `HTTPX2TenacityTransport` re-raises the `httpx2.HTTPStatusError` of the last try with no wrapper. A walk of the full cause chain finds no other case.
- The branch passes the cause to `_provider_http_error`, the method that the `httpx2.HTTPError` branch of the same mapper already calls. It sets the status, masks the detail of the body, and gives `AICredentialsError` for 401 and 403. When the retry transport closed the reply before the SDK read it, `_format_status_error` gets no body and gives the status with no detail.

## Rejected alternatives
- Build the `AIClientError` in `_map_anthropic_errors` from the status of the cause. This repeats the status, masking and credentials logic of `_provider_http_error`, and the two copies can become different.
- Read the status from the text of the exception. The text is not a stable contract, and the masking can change it.
- Give the Anthropic SDK a plain client with no retry transport, and let the SDK retry. The SDK client gets `max_retries=0` because the shared retry transport owns the retries and the `Retry-After` wait of each provider path; a second retry policy for one provider would split that.
- Put the cause lookup in `BaseLLMProviderMixin`. No other provider sends through an SDK that wraps the transport error, so the lookup stays in the Claude mapper.

## ADDED Requirements

### Requirement: Gateway stream error frames carry HTTP status and spend-limit mapping
`LLMClient.chat_stream` SHALL map `openai.APIError` SSE error frames through `_map_openai_error`, raising `AIClientError` with numeric `status`, `AIKeySpendLimitError` for 403 spent-key frames, and `AIClientError` without `openai.APIError` escape for non-numeric codes.

#### Scenario: Keepalive followed by status, credentials, spend-limit, or non-numeric error frame
- **WHEN** a gateway stream sends `: keepalive` followed by an SSE error frame with `code` `"408"`, plain `"403"`, `"403"` with a key-limit body, or `"invalid_request_error"`
- **THEN** consuming `chat_stream` raises `AIClientError` with status 408, credentials `AIClientError` with status 403, `AIKeySpendLimitError`, or `AIClientError` with `status is None`

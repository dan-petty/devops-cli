# ai-client-error-reason Specification

## Purpose
An `AIClientError` states the HTTP status or the timeout of the provider call that failed, so a job can log the cause of a failed model call with no text of the model.

## Requirements

### Requirement: An AI client error states its status or timeout
An `AIClientError` SHALL carry `status`, the HTTP status of the provider's reply, and `timed_out`, whether the call timed out. The gateway, Claude and Ollama paths, their streams and `model_call_error` SHALL set them where they know them. The `reason` of the error SHALL be its error code, then `timeout` when the call timed out or the status is 408 or 504, then the HTTP status with its phrase when known. It SHALL hold none of the message.

#### Scenario: A reply with a status
- **WHEN** a provider replies HTTP 408 with a body that holds `MODEL-TEXT`
- **THEN** the error has status 408, and its `reason` is `LLM_INFERENCE_ERROR, timeout (HTTP 408 Request Timeout)` with no `MODEL-TEXT`

#### Scenario: A call that timed out
- **WHEN** a provider call times out
- **THEN** the error has `timed_out` set, and its `reason` is `LLM_INFERENCE_ERROR, timeout`

#### Scenario: An error with no cause known
- **WHEN** an `AIClientError` has no status and did not time out
- **THEN** its `reason` is `LLM_INFERENCE_ERROR`

#### Scenario: A failed call of an agent run
- **WHEN** an agent run fails with `ModelHTTPError` with status 504, or with `ModelTimeoutError`
- **THEN** `model_call_error` gives an error with status 504, or with `timed_out` set, and its text holds no text of the model

#### Scenario: A status that is not a timeout
- **WHEN** a provider replies HTTP 529
- **THEN** the `reason` is `LLM_INFERENCE_ERROR, HTTP 529`

#### Scenario: A provider with its own error
- **WHEN** a Claude call, or an Ollama call, times out, or Ollama replies HTTP 500
- **THEN** the error has `timed_out` set, or status 500, as the gateway error has

### Requirement: A failed transport names its phase and its error
When the model call of an agent run fails with `ModelConnectionError` or `ModelTimeoutError`, the message of the `AIClientError` from `model_call_error` SHALL name the class of the pydantic-ai error, the phase of the transport when pydantic-ai knows it, and the class and the text of the first error of its cause chain, which is the error of the HTTP library. The text SHALL be masked and cut as other stop text. An error with no cause SHALL keep the message with the class only.

#### Scenario: A dropped stream
- **WHEN** the investigation's model call fails with `ModelConnectionError` in the phase `read`, from an `APIConnectionError`, from `httpx2.RemoteProtocolError("Server disconnected without sending a response.")`
- **THEN** the message is `The investigation's model call failed (ModelConnectionError, phase read, RemoteProtocolError: Server disconnected without sending a response.).`

#### Scenario: A connect timeout with no text
- **WHEN** the call fails with `ModelTimeoutError` in the phase `connect`, from `httpx2.ConnectTimeout("")`
- **THEN** the message is `The investigation's model call failed (ModelTimeoutError, phase connect, ConnectTimeout).`

#### Scenario: No cause
- **WHEN** the call fails with a `ModelConnectionError` that has no cause
- **THEN** the message is `The investigation's model call failed (ModelConnectionError).`

#### Scenario: A secret in the text of the transport error
- **WHEN** the text of the transport error holds an API key
- **THEN** the message names the class of the transport error and does not hold the key

### Requirement: A Claude reply keeps its status after the retries
When the Anthropic SDK raises `APIConnectionError` from the `httpx2.HTTPStatusError` that the retry transport of the shared client raised after its last try, the Claude path SHALL build the error from that status error, as for a status error that the SDK did not wrap. An `APIConnectionError` from another cause SHALL give the connection error with no status.

#### Scenario: A Claude reply 529 through the shared client
- **WHEN** each try of a Claude chat call or stream through the shared client gets HTTP 529
- **THEN** the error has status 529, and its `reason` is `LLM_INFERENCE_ERROR, HTTP 529`

#### Scenario: A Claude reply 401 through the shared client
- **WHEN** a Claude call through the shared client gets HTTP 401
- **THEN** the error is an `AICredentialsError` that names HTTP 401

#### Scenario: A Claude call that cannot connect
- **WHEN** the connection of a Claude call is refused
- **THEN** the error has no status and did not time out

### Requirement: A spent provider key is a spend-limit error
`spend_limit_error` in `ai/client/models.py` SHALL be the one rule for a 401, 402 or 403 reply. It SHALL give `AIKeySpendLimitError`, a subclass of `AICredentialsError`, for a 402 with any body, and for a 401 or 403 whose error text (the `message` or `error` of the body, or the body as a string or a JSON text) holds `Key limit exceeded` with no regard to case. The error text SHALL name the spend limit, the status and the person step, and SHALL hold no text of the body.

#### Scenario: The text of the error
- **WHEN** the rule reads a 403 body whose `message` is the gateway's `litellm.APIError: APIError: OpenrouterException - {"error":{"message":"Key limit exceeded (total limit). ... $5.00 of $5.00 used; does not reset.","code":403}}`
- **THEN** it gives `AIKeySpendLimitError` with the text `The provider key reached its spend limit (HTTP 403). A person raises the spend limit of the key at the provider, or changes the key.`, which holds no `$` amount, no key and no URL

#### Scenario: The text in another field
- **WHEN** a 403 body holds `Key limit exceeded` only in a field that is not `message` or `error`
- **THEN** the rule gives no spend-limit error

#### Scenario: A reply that asks for payment
- **WHEN** the rule reads a 402 whose body is the gateway's `This request requires more credits, or fewer max_tokens` message, another text, or no body
- **THEN** it gives `AIKeySpendLimitError` with the text `The provider key reached its spend limit (HTTP 402). A person raises the spend limit of the key at the provider, or changes the key.`, which holds no amount and no URL of the body

### Requirement: Each refused-key site uses the rule
`model_call_error` and the status branches of `LLMClient` SHALL call `spend_limit_error` for each status of `KEY_STOP_STATUSES` (401, 402, 403), and `fetch_model_info` for a 401 or 403, before they build their credentials error. They SHALL give that credentials error for a 401 or 403 with any other body. `model_call_error` SHALL also give `AIKeySpendLimitError` for a `ModelQuotaExceededError` of pydantic-ai, with the status of the error, or with 402 when it has none.

#### Scenario: A model call of an agent run on a spent key
- **WHEN** an agent run fails with `ModelHTTPError` 403 whose body holds the gateway's key-limit message
- **THEN** `model_call_error` gives `AIKeySpendLimitError`

#### Scenario: A refused key keeps the credentials error
- **WHEN** an agent run fails with `ModelHTTPError` 403 or 401 whose body says `Authentication Error`
- **THEN** `model_call_error` gives an `AICredentialsError` that is not an `AIKeySpendLimitError`, with the text `The model refused the key (HTTP 403).` or `(HTTP 401).`

#### Scenario: A gateway call of LLMClient on a spent key
- **WHEN** a chat or a stream of `LLMClient` through the gateway gets HTTP 403 with the gateway's key-limit body
- **THEN** it raises `AIKeySpendLimitError` after one request, and a 403 with another body still raises the error that names the key sources

#### Scenario: A Claude call on a spent key
- **WHEN** a Claude call through the shared client gets HTTP 403 whose error message holds `Key limit exceeded`
- **THEN** it raises `AIKeySpendLimitError`

#### Scenario: The model list of the gateway on a spent key
- **WHEN** `fetch_model_info` gets HTTP 403 whose body holds `Key limit exceeded`
- **THEN** it raises `AIKeySpendLimitError`

#### Scenario: A model call of an agent run that asks for payment
- **WHEN** an agent run fails with `ModelHTTPError` 402, or with a `ModelQuotaExceededError` that has no HTTP status
- **THEN** `model_call_error` gives `AIKeySpendLimitError` that names HTTP 402, and `failure_class_of` gives the class `spend_limit` for it

#### Scenario: A quota error with another status
- **WHEN** an agent run fails with a `ModelQuotaExceededError` whose HTTP status is 429
- **THEN** `model_call_error` gives `AIKeySpendLimitError` that names HTTP 429

#### Scenario: The cooldown of the gateway is no spent key
- **WHEN** an agent run fails with `ModelHTTPError` 429 whose body says `No deployments available for selected model`
- **THEN** `model_call_error` gives an `AIClientError` that is not an `AICredentialsError`, and `failure_class_of` gives the class `provider`

#### Scenario: A call of LLMClient that asks for payment
- **WHEN** a chat or a stream of `LLMClient` through the gateway, or a Claude call, gets HTTP 402
- **THEN** it raises `AIKeySpendLimitError` after one request

### Requirement: Gateway stream error frames carry HTTP status and spend-limit mapping
`LLMClient.chat_stream` SHALL map `openai.APIError` SSE error frames through `_map_openai_error`, raising `AIClientError` with numeric `status`, `AIKeySpendLimitError` for 403 spent-key frames, and `AIClientError` without `openai.APIError` escape for non-numeric codes.

#### Scenario: Keepalive followed by status, credentials, spend-limit, or non-numeric error frame
- **WHEN** a gateway stream sends `: keepalive` followed by an SSE error frame with `code` `"408"`, plain `"403"`, `"403"` with a key-limit body, or `"invalid_request_error"`
- **THEN** consuming `chat_stream` raises `AIClientError` with status 408, credentials `AIClientError` with status 403, `AIKeySpendLimitError`, or `AIClientError` with `status is None`

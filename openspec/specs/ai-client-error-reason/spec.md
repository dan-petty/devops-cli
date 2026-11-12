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

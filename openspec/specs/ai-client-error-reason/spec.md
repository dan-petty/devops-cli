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

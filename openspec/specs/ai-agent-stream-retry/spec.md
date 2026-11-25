# ai-agent-stream-retry Specification

## Purpose
This specification defines retry behavior for asynchronous Pydantic AI agent requests and streams to handle transient network errors safely without duplicating stream output.

## Requirements

### Requirement: Async retry before first chunk
The pydantic-ai model of a gateway chat group SHALL send a call again when the call never reached the gateway (a `ModelConnectionError` with the phase `connect` or `pool`), or when its stream failed before its first event: an error frame in the stream, a stream that broke, or a stream with no content. A first chunk with only the role is no event.

#### Scenario: Reset before first chunk
- **WHEN** a fake gateway answers the first streamed call with status 200, a keepalive comment and the end of the connection, and answers the second call with a reply
- **THEN** the agent run returns the reply of the second call, and the gateway got 2 calls

#### Scenario: An error frame before the first event
- **WHEN** a fake gateway answers the first streamed call with status 200 and an error frame with code 408, or with a first chunk that holds only the role and then that error frame, and answers the second call with a reply
- **THEN** the agent run returns the reply of the second call, and the gateway got 2 calls

#### Scenario: A connect that fails
- **WHEN** the connect of the first call fails and the second call gets a reply
- **THEN** the agent run returns the reply, and the transport saw 2 calls

### Requirement: No replay after output
The pydantic-ai model of a gateway chat group MUST NOT send a call again after its stream emitted its first event. The failure SHALL end the call once.

#### Scenario: Reset after first chunk
- **WHEN** a fake gateway answers a streamed call with status 200, one chunk of text and then the end of the connection
- **THEN** the agent run raises `ModelConnectionError` with the phase `read`, and the gateway got 1 call

#### Scenario: An error frame after the first event
- **WHEN** a fake gateway answers a streamed call with status 200, one chunk of text and then an error frame with code 408
- **THEN** the agent run raises `ModelHTTPError` with `in_stream` set, and the gateway got 1 call

### Requirement: Bounded retry attempts
The pydantic-ai model of a gateway chat group SHALL send a call at most `ai.max_retries` + 1 times, with no wait between the sends. When each send fails, it SHALL raise the error of the last send, not a `FallbackExceptionGroup`. The OpenAI SDK under it SHALL make no retry of its own.

#### Scenario: Retry limit reached
- **WHEN** `ai.max_retries` is 2 and each connect fails
- **THEN** the transport saw 3 calls, and the run raises `ModelConnectionError` with the phase `connect`

#### Scenario: Each stream fails before its first event
- **WHEN** `ai.max_retries` is 1 and the fake gateway answers each streamed call with status 200 and an error frame with code 408
- **THEN** the gateway got 2 calls, and the run raises `ModelHTTPError` with status 408

### Requirement: Non-retryable failures
The pydantic-ai model of a gateway chat group MUST NOT send a call again when the gateway answered it with an HTTP status, because the gateway retried it already.

#### Scenario: The gateway answers 503
- **WHEN** `ai.max_retries` is 3 and the fake gateway answers a streamed call with status 503
- **THEN** the gateway got 1 call, and the run raises `ModelHTTPError` with status 503

#### Scenario: Authentication failure
- **WHEN** the fake gateway answers a call with status 401
- **THEN** the gateway got 1 call, and the run raises `ModelHTTPError` with status 401

### Requirement: Provider uses retry transport
`create_pydantic_ai_provider` SHALL build the HTTP client of a provider that is not a gateway chat group with the async retry transport. The HTTP client of a gateway chat group (`gateway_caller` with a provider other than `system-one` or `typesafe`) SHALL have no retry transport.

#### Scenario: Provider client transport
- **WHEN** the provider builds its async client for `openai` with no gateway caller
- **THEN** the client transport is the async retry transport

#### Scenario: Gateway client transport
- **WHEN** the provider builds its async client for `openai` with `gateway_caller`, and for `system-one` with `gateway_caller`
- **THEN** the transport of the `openai` client is not the async retry transport, and the transport of the `system-one` client is

### Requirement: GitHub session unchanged
The GitHub session MUST keep its own retry rules and MUST NOT opt in to the new retry policy.

#### Scenario: GitHub session client
- **WHEN** the GitHub session builds its async client
- **THEN** the client has no retry transport from this change.

### Requirement: One deadline over all sends of a gateway call
The pydantic-ai model of a gateway chat group SHALL set the model setting `request_timeout` to `ai.request_timeout_seconds` unless the run sets one. The deadline SHALL start once for a call and SHALL cover every send of it and the read of its stream. A call past the deadline SHALL raise `ModelRequestTimeout` and SHALL get no further send.

#### Scenario: The default deadline
- **WHEN** a gateway chat model is resolved with `ai.request_timeout_seconds` 300
- **THEN** its settings hold `request_timeout` 300 and `max_retries` 0

#### Scenario: A second send that answers after the deadline of the call
- **WHEN** `request_timeout` is 0.5 s, the first send fails before its first event after 0.4 s, and the second send answers 0.3 s after it starts
- **THEN** the run raises `ModelRequestTimeout` with the timeout 0.5 s, after 2 sends

### Requirement: First content event deadline on stalled gateway streams
`GatewayCallModel` SHALL set `ModelSettings["first_event_timeout"]` from `ai.first_token_timeout_seconds` (default `60` s) on streamed gateway calls without applying it at the outer whole-call deadline wrapper, closing stalled sends at the deadline. `model_call_error` SHALL report `timed_out=True` for `ModelRequestTimeout`.

#### Scenario: Stalled keep-alive stream times out before second keep-alive and exhausts retries
- **WHEN** a fake gateway emits SSE `: ping` keep-alive comments every `0.4` s with no content event and `GatewayCallModel` uses `first_token_timeout=0.2` and `max_retries=0`
- **THEN** the run raises `ModelRequestTimeout` with `setting == "first_event_timeout"` before a second keep-alive arrives, and `model_call_error` reports `timed_out is True`

### Requirement: Bounded resend on first-event timeout only before the first content event
`failed_before_first_event` SHALL return `True` for `ModelRequestTimeout` only when `error.setting == "first_event_timeout"`, resending stalled attempts up to `ai.max_retries` times. Pauses after the first content event SHALL NOT trigger `first_event_timeout`.

#### Scenario: Stalled first attempt resends once and slow tokens after the first token succeed
- **WHEN** `ai.max_retries` is `1`, a stalled keep-alive send retries against a valid second reply, and another run emits content then pauses longer than `first_token_timeout`
- **THEN** the stalled run retries once (`2` gateway calls) and closes the first stream, while the slow post-first-token stream completes in `1` call

### Requirement: First-token deadline validates below request_timeout_seconds and updates generated docs
`AIConfig` SHALL define `first_token_timeout_seconds` (`ge=1`, default `60`), SHALL reject `first_token_timeout_seconds >= request_timeout_seconds` naming both settings, and generated settings docs (`docs/CONFIGURATION.md`, `docs/ENV_VARS.md`) SHALL list `ai.first_token_timeout_seconds`.

#### Scenario: Invalid timeout nesting and default value
- **WHEN** `Settings()` loads with defaults and `AIConfig` is validated with `first_token_timeout_seconds=120` and `request_timeout_seconds=90`
- **THEN** the default is `60` and validation raises an error naming `ai.first_token_timeout_seconds` and `ai.request_timeout_seconds`

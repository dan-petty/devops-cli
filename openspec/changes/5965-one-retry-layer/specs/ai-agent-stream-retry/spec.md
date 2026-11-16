## MODIFIED Requirements

### Requirement: Async retry before first chunk
The pydantic-ai model of a gateway chat group SHALL send a call again when the call failed before it reached the gateway: a `ModelConnectionError` with the phase `connect` or `pool`. It SHALL send a streamed call again when the stream failed before its first event: an error frame inside the stream (`ModelAPIError.in_stream`), a stream that broke (a `ModelConnectionError` that is not a `ModelTimeoutError`), or a stream that ended with no content (`UnexpectedModelBehavior`). A first chunk that holds only the role is no event.

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

## ADDED Requirements

### Requirement: One deadline over all sends of a gateway call
The pydantic-ai model of a gateway chat group SHALL set the model setting `request_timeout` to `ai.request_timeout_seconds` unless the run sets one. The deadline SHALL start once for a call and SHALL cover every send of it and the read of its stream. A call past the deadline SHALL raise `ModelRequestTimeout` and SHALL get no further send.

#### Scenario: The default deadline
- **WHEN** a gateway chat model is resolved with `ai.request_timeout_seconds` 300
- **THEN** its settings hold `request_timeout` 300 and `max_retries` 0

#### Scenario: A second send that answers after the deadline of the call
- **WHEN** `request_timeout` is 0.5 s, the first send fails before its first event after 0.4 s, and the second send answers 0.3 s after it starts
- **THEN** the run raises `ModelRequestTimeout` with the timeout 0.5 s, after 2 sends

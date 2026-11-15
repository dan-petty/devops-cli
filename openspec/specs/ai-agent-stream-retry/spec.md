# ai-agent-stream-retry Specification

## Purpose
This specification defines retry behavior for asynchronous Pydantic AI agent requests and streams to handle transient network errors safely without duplicating stream output.

## Requirements

### Requirement: Async retry before first chunk
The async agent client SHALL retry a model request after a connect error or a reset that happens before the first response chunk.

#### Scenario: Reset before first chunk
- **WHEN** the first model request raises ConnectionResetError before it yields a chunk and the second attempt returns a complete reply
- **THEN** the agent run returns the second reply and raises no AIClientError.

### Requirement: No replay after output
The async agent client MUST NOT send a model request again after the response stream emitted its first chunk.

#### Scenario: Reset after first chunk
- **WHEN** the model response yields one chunk and then raises ConnectionResetError
- **THEN** the run raises AIClientError and sends no second request.

### Requirement: Bounded retry attempts
The async retry SHALL stop after three attempts and SHALL use backoff between them.

#### Scenario: Retry limit reached
- **WHEN** each of three attempts raises ConnectionResetError before the first chunk
- **THEN** the client sends exactly three attempts, waits between them, and raises AIClientError.

### Requirement: Non-retryable failures
The async retry MUST NOT retry an HTTP 4xx response.

#### Scenario: Authentication failure
- **WHEN** the model request returns HTTP 401 before any chunk
- **THEN** the client sends one request and raises AIClientError.

### Requirement: Provider uses retry transport
create_pydantic_ai_provider SHALL build its async client with the retry policy.

#### Scenario: Provider client transport
- **WHEN** the provider builds its async client
- **THEN** the client transport is the async retry transport.

### Requirement: GitHub session unchanged
The GitHub session MUST keep its own retry rules and MUST NOT opt in to the new retry policy.

#### Scenario: GitHub session client
- **WHEN** the GitHub session builds its async client
- **THEN** the client has no retry transport from this change.

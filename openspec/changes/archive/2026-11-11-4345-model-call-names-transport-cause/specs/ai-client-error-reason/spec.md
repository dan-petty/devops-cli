## ADDED Requirements

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

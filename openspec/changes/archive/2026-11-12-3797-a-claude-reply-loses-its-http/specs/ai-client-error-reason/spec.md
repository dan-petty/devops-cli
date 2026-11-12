## ADDED Requirements

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

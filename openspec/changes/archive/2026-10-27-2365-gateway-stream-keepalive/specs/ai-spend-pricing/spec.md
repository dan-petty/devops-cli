## ADDED Requirements

### Requirement: A chat call that fails in its stream is recorded as a failed attempt
When a chat call that returns one reply fails after its status line, because of an error frame, a cut stream or the response size limit, devops-cli SHALL record one row in the spend ledger with the request type `chat_dispatch`, finish reason `error`, 0 prompt and 0 completion tokens, and the serving backend that the response headers name.

#### Scenario: An error frame after a ping
- **WHEN** a chat call gets a stream with a `: ping` comment and then an error frame with `code` `"500"`
- **THEN** the spend ledger has one row with the request type `chat_dispatch` and finish reason `error`

## Purpose

How an OpenAI-compatible chat call reads its reply: as a stream that the gateway keeps open with keepalive comments, joined into one reply, with the response size limit, and with a failure in the stream reported as the error of its status.

## ADDED Requirements

### Requirement: The gateway keeps a streamed chat reply open
The gateway config SHALL set `litellm_settings.sse_keepalive_ping_interval_seconds` to a number of seconds that is more than 0 and less than 125, the Proxy Read Timeout of the Cloudflare edge.

#### Scenario: The gateway config
- **WHEN** the gateway config `k8s/llm/gateway/config.yaml` is read
- **THEN** `litellm_settings.sse_keepalive_ping_interval_seconds` is more than 0 and less than 125

### Requirement: An OpenAI-compatible chat call reads its reply as a stream
A chat call that returns one reply from the `gateway`, `openai` or `copilot` provider SHALL send `stream: true` with `stream_options.include_usage`, and SHALL return the content, the reasoning, the token usage, the finish reason, the model and the serving backend of the streamed chunks. It SHALL ignore SSE comment lines.

#### Scenario: A reply that starts with keepalive comments
- **WHEN** the gateway answers a chat call with two `: ping` comments, then reasoning chunks, content chunks with the finish reason `stop`, a usage chunk and `[DONE]`
- **THEN** the call sends `stream: true` and returns the joined content, the joined reasoning, the finish reason `stop`, the model of the chunks, the prompt, completion and reasoning token counts of the usage chunk, and the serving backend of the response headers

### Requirement: A failure in the stream has the error of its status
When the stream of a chat call holds an error frame whose `code` is an HTTP status, the call SHALL fail with the error that an HTTP reply with that status and that error body gives.

#### Scenario: An error frame after a ping
- **WHEN** the gateway answers a chat call with a `: ping` comment, then `data: {"error": {"message": "backend failed", "code": "500"}}` and `[DONE]`
- **THEN** the call fails with the same `AIClientError` message as an HTTP 500 reply with that error body

#### Scenario: A refused key in the stream
- **WHEN** the stream of a chat call holds an error frame with `code` `"401"`
- **THEN** the call fails with the credentials error of an HTTP 401 reply

### Requirement: A streamed chat reply has the response size limit
A chat call SHALL fail with the response size error when the decoded data of its stream passes `DEFAULT_AI_MAX_RESPONSE_BYTES`.

#### Scenario: A stream larger than the limit
- **WHEN** the data of the chunks of a chat reply passes the response size limit
- **THEN** the call fails with the response size error

### Requirement: A cut stream fails
A chat call SHALL fail with "Provider stream ended before its final frame." when its stream ends with no `[DONE]` frame and no finish reason.

#### Scenario: A stream that stops after one chunk
- **WHEN** the gateway answers a chat call with one content chunk and then closes the stream
- **THEN** the call fails with "Provider stream ended before its final frame."

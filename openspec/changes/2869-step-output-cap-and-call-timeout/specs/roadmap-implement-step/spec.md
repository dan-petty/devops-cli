# Spec Delta

## MODIFIED Requirements

### Requirement: A failed model call gives a reason with the error text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status when it has one, and the name of the model. For a `ModelHTTPError` it SHALL also hold the error text of the body, masked and cut like other stop text, without a quoted part, a second line, or what follows the first `=` or `;`. For a `ModelRequestTimeout` it SHALL hold the deadline in seconds. It SHALL hold no other value of the body and not the message of the error.

#### Scenario: The body of a 400
- **WHEN** the body of a `ModelHTTPError` with the status 400 is a dict with the `message` "XML syntax error on line 75: unexpected EOF"
- **THEN** the reason is "ModelHTTPError: HTTP 400, model example-model, body: XML syntax error on line 75: unexpected EOF"

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key` and no error text
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: A token in the body
- **WHEN** the error text of the body holds a token in the form of a GitHub token, or is longer than the limit of stop text
- **THEN** the reason holds the text with the token masked, cut to the limit

#### Scenario: A body that echoes the model
- **WHEN** the error text of the body is "error parsing tool call: raw='{...DB_PASSWORD=hunter2...}', err=EOF", or holds a key and value such as "api_key=abc", or an unclosed quote, or a second line
- **THEN** the reason holds the first line up to the quoted part or the first `=` or `;`, and no value of the echo

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error after it, and the checkout is reset

#### Scenario: The deadline
- **WHEN** a model call raises a `ModelRequestTimeout` for a deadline of 600 seconds
- **THEN** the reason is "ModelRequestTimeout: model example-model, no complete reply in 600 seconds"

## ADDED Requirements

### Requirement: A model reply has an output cap and a call has a deadline
The agent of a step SHALL set the model settings `max_tokens` to `CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS` and `request_timeout` to `CONST_ROADMAP_IMPLEMENT_REQUEST_TIMEOUT_SECONDS`. The deadline SHALL be less than the timeout of the router in `k8s/llm/gateway/config.yaml`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap and the deadline

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: The deadline is short of the router timeout
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** the deadline is less than that timeout

#### Scenario: A call that never ends
- **WHEN** a model call does not answer within the deadline
- **THEN** the step reports stopped with a reason that starts with `ModelRequestTimeout: ` and holds the deadline, the model got one request, and the checkout is reset

### Requirement: A reply that reaches the output cap stops the step with its cause
A turn whose reply has the finish reason `length`, or that Pydantic AI ends with `IncompleteToolCall`, SHALL end the step as stopped, and the step SHALL reset the checkout. The reason SHALL name the cap and its value. The step SHALL not send the request again. A reply of a size under the cap SHALL pass.

#### Scenario: A reply that the cap ends
- **WHEN** the model answers with a text and the finish reason `length`
- **THEN** the step reports stopped, the reason holds `CONST_ROADMAP_IMPLEMENT_MAX_OUTPUT_TOKENS` as a number, the model got one request, and the checkout is reset

#### Scenario: A tool call that the cap cuts
- **WHEN** the model answers with a tool call whose arguments are not whole and the finish reason `length`
- **THEN** the step reports stopped with the same reason, and the model got one request

#### Scenario: A reply of the longest honest size
- **WHEN** the model answers with a `write_file` call of a file of about 12,000 tokens and the finish reason `tool_calls`, and then ends the run
- **THEN** the step ends done

# roadmap-implement-step/model-calls Specification

## Purpose
The model calls of an implement step: the output cap and the deadline of a call, the failures of a call and of a stream, the refused key, and the ladder of the step classes.

## Requirements

### Requirement: A failed model call ends the step stopped
A run that ends on a failed model call (a `ModelAPIError` that is not a refused key) SHALL end as stopped when no tier of its ladder remains, and the step SHALL reset the checkout. The outcome of a failed turn SHALL hold the requests and the tokens that the turn spent, the failed request included, and the last text of the model, added to those of the turn before it.

#### Scenario: A model call fails in the first turn
- **WHEN** the agent writes `src/sample.py` and a new test file, and its next model call raises a `ModelAPIError`, a `ModelHTTPError` with the status 503, or a `ModelRequestTimeout`, and no tier of the ladder remains
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of both files, the requests (the reply and the failed request) and the tokens, and the last text of the model, and the checkout is reset

#### Scenario: A model call fails in the extra turn
- **WHEN** the first turn passes every check and leaves a task unticked, and the model call of the extra turn for the ticks raises one of those errors, and no tier of the ladder remains
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of the work of the first turn, the requests of both turns, and the last text of the first turn, and the checkout is reset

### Requirement: A change_tier failure advances the ladder
When the failure classification maps the failure to `change_tier`, or a model call fails without a key refusal, and the ladder for that step class has another tier available, the step SHALL advance to the next tier without incrementing the repair round counter.

#### Scenario: A parser failure advances to the next tier
- **WHEN** an attempt encounters an error classified as `change_tier` and another tier remains in the ladder
- **THEN** the next attempt runs on the next tier of the ladder and the repair round counter does not change

#### Scenario: A provider error advances to the next tier
- **WHEN** a model call raises a `ModelAPIError` that is not a refused key and another tier remains in the ladder
- **THEN** the next attempt runs on the next tier of the ladder and the repair round counter does not change

#### Scenario: Ladder tiers exhausted
- **WHEN** an attempt encounters an error classified as `change_tier` and no further tiers remain in the ladder
- **THEN** the step stops and resets the checkout

### Requirement: A failed model call gives a reason with the error text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status if any, and the name of the model. For a `ModelHTTPError` it SHALL also hold the first line of the error text of the body: masked, cut like other stop text, without quoted parts, and ending at the first `=` or `;`. A gateway dict `{'error': '<text>'}` ending that line is read as `<text>`. For a `ModelRequestTimeout` it SHALL hold the deadline in seconds. It SHALL hold no other value.

#### Scenario: The body of a 400
- **WHEN** the body of a `ModelHTTPError` with the status 400 is a dict with the `message` "XML syntax error on line 75: unexpected EOF"
- **THEN** the reason is "ModelHTTPError: HTTP 400, model example-model, body: XML syntax error on line 75: unexpected EOF"

#### Scenario: The gateway wrapper
- **WHEN** the message of the body is "litellm.BadRequestError: Ollama_chatException - KeyError: 'message', Got unexpected response from Ollama: {'error': 'XML syntax error on line 70: unexpected EOF'}"
- **THEN** the reason holds "XML syntax error on line 70: unexpected EOF"

#### Scenario: A token in the gateway wrapper
- **WHEN** the error text inside the gateway wrapper holds a token in the form of a GitHub token
- **THEN** the reason holds the text with the token masked

#### Scenario: A quoted secret
- **WHEN** the error text of the body, with or without the wrapper, holds a quoted part such as "db_password: hunter2" that has no `=` and no known secret form
- **THEN** the reason holds `<text>` in place of the quoted part

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key` and no error text
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: A token in the body
- **WHEN** the error text of the body holds a token in the form of a GitHub token, or is longer than the limit of stop text
- **THEN** the reason holds the text with the token masked, cut to the limit

#### Scenario: A body that echoes the model
- **WHEN** the error text of the body is "error parsing tool call: raw='{...DB_PASSWORD=hunter2...}', err=EOF", or holds a key and value such as "api_key=abc", or an unclosed quote, or a second line
- **THEN** the reason holds the first line up to the first `=` or `;`, with each quoted part hidden, and no value of the echo

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error after it, and the checkout is reset

#### Scenario: The deadline
- **WHEN** a model call raises a `ModelRequestTimeout` for a deadline of 600 seconds
- **THEN** the reason is "ModelRequestTimeout: model example-model, no complete reply in 600 seconds"

### Requirement: A refused key stops the whole run
A model call that fails with a `ModelHTTPError` of the status 401 or 403 SHALL raise `AICredentialsError` out of the step after the checkout is reset, and the job SHALL NOT run the next item.

#### Scenario: A refused key in the first turn
- **WHEN** the model call raises a `ModelHTTPError` with the status 401
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in the extra turn
- **WHEN** the first turn fails `ruff check`, and the model call of the extra turn raises a `ModelHTTPError` with the status 401 or 403
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in a job
- **WHEN** the model call of the first step of an item raises a `ModelHTTPError` with the status 401
- **THEN** `apply_implement` raises `AICredentialsError`, and the item gets no stop comment

### Requirement: A failure of the generation inside a stream names a known cause
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the reason of the stopped step SHALL hold one more line, after the line of the class, the status and the body. The line SHALL say that the provider failed inside the stream and that tool call parsing failed is a known cause. The step SHALL choose the line by the fields of the error and not by its text.

#### Scenario: A failure inside a stream
- **WHEN** a model call fails with a 400 inside an open stream, and every send fails
- **THEN** the reason holds a line that says tool call parsing failed is a known cause, after the line of the class, the status and the body

#### Scenario: A failure outside a stream
- **WHEN** a model call fails with a 400 that is not inside a stream, or with a 503
- **THEN** the reason holds no such line

### Requirement: An error of the generation inside a stream is sent again
When a model call fails with a `ModelHTTPError` of the status 400 inside an open stream that is no context window error, the step SHALL send the request again, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times in a row. The first such failure on a tier SHALL add a message that asks for a smaller edit to the request. The next one on the same tier SHALL end the turn with no send. After the last send, the step SHALL stop with the reason of the failed call and the class `parser`.

#### Scenario: Two separate failures
- **WHEN** a model request fails with a 400 inside a stream, a good reply follows, and a later request fails the same way
- **THEN** the step stops with the class `parser`, and the later request is not sent again

#### Scenario: A new tier
- **WHEN** the first tier of the ladder ends on a second parser failure, and the first request of the next tier fails with a 400 inside a stream
- **THEN** the request is sent again with the message that asks for a smaller edit

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the messages of the first and one more part at its end, the message that asks for a smaller edit

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops with the class `parser`, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests, the last one with the smaller-edit message

#### Scenario: The work of the group stays
- **WHEN** the agent ticks the first task of a group and the verification of it passes, then two requests fail with a 400 inside a stream
- **THEN** the step stops with the class `parser`, and the branch holds the `wip:` commit of the first task

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: The failed send counts in the limit
- **WHEN** the replies and the failed send reach `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS`
- **THEN** the model gets no more than that many requests, and the step stops with the reason of the request limit

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for a failed static check fails once with a 400 inside a stream
- **THEN** the request is sent again with the message that asks for a smaller edit, and the extra turn ends with the check passing

### Requirement: A model reply has an output cap and a call has a deadline
The agent of a step SHALL set the model settings `max_tokens` to the context window of the task divided by `CONST_ROADMAP_IMPLEMENT_OUTPUT_WINDOW_SHARE`, and `request_timeout` to the setting `roadmap.implement.request_timeout_seconds`. The default of the deadline SHALL be less than the timeout of the router in `k8s/llm/gateway/config.yaml`. A call that runs past the deadline SHALL end the step as stopped, and the model SHALL get no second request for it.

#### Scenario: The settings of the first request
- **WHEN** the step makes its first model request
- **THEN** the model settings of the request hold the cap, a quarter of the window, and the deadline of the setting

#### Scenario: The cap reaches the wire
- **WHEN** the agent of a step sends a request to an OpenAI chat model
- **THEN** the body of the request holds `max_completion_tokens` with the value of the cap, and no `request_timeout`

#### Scenario: The deadline is short of the router timeout
- **WHEN** a test reads `router_settings.timeout` of the gateway config
- **THEN** the default of the deadline is less than that timeout

#### Scenario: A call that never ends
- **WHEN** a model call does not answer within the deadline
- **THEN** the step reports stopped with a reason that starts with `ModelRequestTimeout: ` and holds the deadline, the model got one request, and the checkout is reset

### Requirement: A reply that reaches the output cap stops the step with its cause
A model reply with the finish reason `length` SHALL end the run at once, without a further request or tool call. The step SHALL end as stopped, and SHALL reset the checkout. The reason SHALL start with `OutputCapReached: ` and SHALL hold the cap. The request SHALL count in the requests and the spend of the step, and the step SHALL not send it again. A reply of a size under the cap SHALL pass.

#### Scenario: A reply that the cap ends
- **WHEN** the model answers with a text and the finish reason `length`
- **THEN** the step reports stopped with a reason that holds the cap as a number, the model got one request, the outcome counts one request, and the checkout is reset

#### Scenario: A tool call that the cap cuts
- **WHEN** the model answers with a `write_file` call whose arguments are not whole and the finish reason `length`
- **THEN** the step reports stopped with the same reason, the model got one request, the tool did not run, and the checkout is reset

#### Scenario: The counts stay in the reason
- **WHEN** the shell tool refused one command, and a later reply has the finish reason `length`
- **THEN** the reason holds the cap, and then the count of the refused commands

#### Scenario: A reply under the cap
- **WHEN** the model answers with a `write_file` call of three quarters of the cap and the finish reason `tool_calls`, and then ends the run
- **THEN** the step ends done

### Requirement: The ladder names only the step classes that a step reads
The step classes SHALL be `edit`, which is a group of a change, and `repair`, which is the fix of a failed check. The setting `roadmap.implement.ladder` SHALL hold a tier list for each of these two classes by default, and SHALL refuse a key that is not one of them, with a message that names the key and the classes.

#### Scenario: The default ladder
- **WHEN** the settings are read with no ladder set
- **THEN** the ladder holds the keys `edit` and `repair`, and no other key

#### Scenario: A removed class is named
- **WHEN** the ladder names the key `plan` or `review`
- **THEN** the settings are refused with a message that the ladder names no step class with that key

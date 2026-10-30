# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: A failed model call gives a reason with no text of the provider`
- TO: `### Requirement: A failed model call gives a reason with the error text of the provider`

## MODIFIED Requirements

### Requirement: A failed model call gives a reason with the error text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status when it has one, and the name of the model. For a `ModelHTTPError` it SHALL also hold the error text of the body, masked and cut like other stop text. It SHALL hold no other value of the body and not the message of the error.

#### Scenario: The body of a 400
- **WHEN** the body of a `ModelHTTPError` with the status 400 is a dict with the `message` "XML syntax error on line 75: unexpected EOF"
- **THEN** the reason is "ModelHTTPError: HTTP 400, model example-model, body: XML syntax error on line 75: unexpected EOF"

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key` and no error text
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: A token in the body
- **WHEN** the error text of the body holds a token in the form of a GitHub token, or is longer than the limit of stop text
- **THEN** the reason holds the text with the token masked, cut to the limit

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error after it, and the checkout is reset

## ADDED Requirements

### Requirement: An error of the generation inside a stream is sent again once
When a model call fails with a `ModelHTTPError` of the status 400 that the provider reported inside an open stream, and that is no context window error, the step SHALL send the request again with the same history, at most `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` times. The limits of the step SHALL count the requests and tool calls of both sends. After the last send, the step SHALL stop with the reason of a failed model call.

#### Scenario: One failed send
- **WHEN** the first model request fails with a 400 inside a stream, and the second request answers with a good reply that ends the run
- **THEN** the step ends done, and the second request holds the same messages as the first

#### Scenario: Every send fails
- **WHEN** every model request fails with a 400 inside a stream with the body "XML syntax error on line 75: unexpected EOF"
- **THEN** the step stops, the reason holds the body, and the model got `CONST_ROADMAP_IMPLEMENT_MODEL_RESENDS` plus one requests

#### Scenario: Other failed model calls
- **WHEN** a model request fails with a 400 that is not inside a stream, a 503, or a 400 that is a context window error
- **THEN** the model gets no second request, and the step stops

#### Scenario: A failure in the extra turn
- **WHEN** the model request of the extra turn for the ticks fails once with a 400 inside a stream
- **THEN** the request is sent again, and the extra turn ends with the ticks

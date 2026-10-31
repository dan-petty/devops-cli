# Spec Delta

## MODIFIED Requirements

### Requirement: A failed model call gives a reason with the error text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status when it has one, and the name of the model. For a `ModelHTTPError` it SHALL also hold the error text of the body, masked and cut like other stop text, without a second line or what follows the first `=` or `;`. The quoted words of the text SHALL stay, with a secret masked. When the call failed inside an open stream with the status 400 and the error is no context window error, the reason SHALL hold one more line that says the provider failed inside the stream and that tool call parsing failed is a known cause. For a `ModelRequestTimeout` it SHALL hold the deadline in seconds. It SHALL hold no other value of the body and not the message of the error.

#### Scenario: The body of a 400
- **WHEN** the body of a `ModelHTTPError` with the status 400 is a dict with the `message` "XML syntax error on line 75: unexpected EOF"
- **THEN** the reason is "ModelHTTPError: HTTP 400, model example-model, body: XML syntax error on line 75: unexpected EOF"

#### Scenario: Quoted words of the error text
- **WHEN** the message of the body is "litellm.BadRequestError: Ollama_chatException - KeyError: 'message', Got unexpected response from Ollama: {'error': 'XML syntax error on line 70: unexpected EOF'}"
- **THEN** the reason holds that text with its quotes

#### Scenario: A token in a quoted word
- **WHEN** the error text of the body holds a token in the form of a GitHub token inside a quoted word
- **THEN** the reason holds the quoted word with the token masked

#### Scenario: A failure inside a stream
- **WHEN** a model call fails with a 400 inside an open stream, and every send fails
- **THEN** the reason holds a line that says tool call parsing failed is a known cause, after the line of the class, the status and the body

#### Scenario: A failure outside a stream
- **WHEN** a model call fails with a 400 that is not inside a stream, or with a 503
- **THEN** the reason holds no such line

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key` and no error text
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: A token in the body
- **WHEN** the error text of the body holds a token in the form of a GitHub token, or is longer than the limit of stop text
- **THEN** the reason holds the text with the token masked, cut to the limit

#### Scenario: A body that echoes the model
- **WHEN** the error text of the body is "error parsing tool call: raw='{...DB_PASSWORD=hunter2...}', err=EOF", or holds a key and value such as "api_key=abc", or an unclosed quote, or a second line
- **THEN** the reason holds the first line up to the first `=` or `;`, and no value of the echo

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error after it, and the checkout is reset

#### Scenario: The deadline
- **WHEN** a model call raises a `ModelRequestTimeout` for a deadline of 600 seconds
- **THEN** the reason is "ModelRequestTimeout: model example-model, no complete reply in 600 seconds"

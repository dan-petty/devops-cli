# Spec Delta

## ADDED Requirements

### Requirement: A failed model call ends the step stopped
A run that ends on a failed model call (a `ModelAPIError` that is not a refused key) SHALL end as stopped, and the step SHALL reset the checkout. The outcome of a failed turn SHALL hold the requests and the tokens that the turn spent, the failed request included, and the last text of the model, added to those of the turn before it.

#### Scenario: A model call fails in the first turn
- **WHEN** the agent writes `src/sample.py` and a new test file, and its next model call raises a `ModelAPIError`, a `ModelHTTPError` with the status 503, or a `ModelRequestTimeout`
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of both files, the requests (the reply and the failed request) and the tokens, and the last text of the model, and the checkout is reset

#### Scenario: A model call fails in the extra turn
- **WHEN** the first turn passes every check and leaves a task unticked, and the model call of the extra turn for the ticks raises one of those errors
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of the work of the first turn, the requests of both turns, and the last text of the first turn, and the checkout is reset

### Requirement: A failed model call gives a reason with no text of the provider
The reason of a step that a failed model call ended SHALL hold the class of the error, the HTTP status when it has one, and the name of the model. It SHALL NOT hold the message or the body of the reply. When git cannot give the diff of the discarded work, the outcome SHALL hold an empty diff, and the reason SHALL hold the text of the git error after the reason of the stop.

#### Scenario: A message and a body of a failed model call
- **WHEN** the message of a `ModelAPIError` holds a token in the form of a GitHub token, or the body of a `ModelHTTPError` is a dict with the values of the keys `x-api-key` and `api_key`
- **THEN** the reason holds neither the token nor the values, and it is the class, the status when there is one, and the name of the model

#### Scenario: The diff cannot be read
- **WHEN** a model call fails and `git add` or `git diff` fails when the step reads the diff of the discarded work
- **THEN** the step reports stopped with an empty diff, the reason starts with the class of the error and holds the text of the git error, and the checkout is reset

### Requirement: A refused key stops the whole run
A model call that fails with a `ModelHTTPError` of the status 401 or 403 SHALL raise `AICredentialsError` out of the step after the checkout is reset, and the job SHALL NOT run the next item.

#### Scenario: A refused key in the first turn
- **WHEN** the model call raises a `ModelHTTPError` with the status 401
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in the extra turn
- **WHEN** the first turn passes every check, and the model call of the extra turn raises a `ModelHTTPError` with the status 401 or 403
- **THEN** `run_step` raises `AICredentialsError` and the checkout is reset

#### Scenario: A refused key in a job
- **WHEN** the model call of the first step of an item raises a `ModelHTTPError` with the status 401
- **THEN** `apply_implement` raises `AICredentialsError`, and the item gets no stop comment

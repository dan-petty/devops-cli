# Spec Delta

## ADDED Requirements

### Requirement: The warning of a failed model call names the repository and the cause
Refine SHALL write one warning for an item whose model call failed. It SHALL name the repository and the item number, the class of the error, and the `reason` of the `AIClientError`: its error code with its HTTP status or `timeout`. The error that ends the round, the job record and the comments on the issue SHALL keep their text.

#### Scenario: A failed call names the repository and the status
- **WHEN** the model call for #42 of the repository `example/one` fails with an `AIClientError` whose status is 408
- **THEN** the warning holds `#42 in example/one`, `LLM_INFERENCE_ERROR` and `HTTP 408 Request Timeout`

#### Scenario: A failed call that timed out
- **WHEN** the model call fails with an `AIClientError` that timed out
- **THEN** the warning holds `LLM_INFERENCE_ERROR` and `timeout`

#### Scenario: A warning names a timeout
- **WHEN** the model call fails with an `AIClientError` whose status is 408
- **THEN** the warning holds `timeout`

#### Scenario: A failed call with no status
- **WHEN** the model call fails with an `AIClientError` that has no status and did not time out
- **THEN** the warning holds `LLM_INFERENCE_ERROR` and no status

#### Scenario: A failed item keeps its error text
- **WHEN** the model call fails for an item and the round ends
- **THEN** the error of the round names the item with the class of the error and the count of schema violations, as before

### Requirement: The warning of a stopped investigation names the repository and the message
Refine SHALL write one warning for an item whose investigation stopped with no proposal. It SHALL name the repository and the item number, the class of the pydantic-ai error, and the fixed description in the first line of its `message`, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters. It SHALL NOT hold the `body` of the error, a later line of the message, data of the model's reply, or a control character.

#### Scenario: A stopped investigation gives the message
- **WHEN** the investigation of #1 in `example/two` stops with `UnexpectedModelBehavior` whose message is `Exceeded maximum output retries (3)`
- **THEN** the warning holds `#1 in example/two`, `UnexpectedModelBehavior` and `Exceeded maximum output retries (3)`

#### Scenario: The body of the error stays out
- **WHEN** the investigation stops with `UnexpectedModelBehavior` whose body is `MODEL-TEXT`, and whose message has the second line `input_value=MODEL-TEXT`
- **THEN** the warning holds the first line of the message, and neither the body nor the second line

#### Scenario: A secret in the message
- **WHEN** the first line of the message holds a token in the form of a GitHub token
- **THEN** the warning holds the mask in place of the token

#### Scenario: Data of the reply in the message
The fixed description is the text before a quoted part, a `:`, a `;` or a `=`, because pydantic-ai writes data of the reply after those marks.
- **WHEN** the investigation stops with `UnexpectedModelBehavior` whose message is ``Function tool calls must have unique `tool_call_id` values; duplicate `tool_call_id`s: ['MODEL-ID']``
- **THEN** the warning holds `Function tool calls must have unique <text> values` and no `MODEL-ID`

#### Scenario: A control character in the message
- **WHEN** the first line of the message holds an escape or a null character
- **THEN** the warning holds neither

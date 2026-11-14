## ADDED Requirements

### Requirement: A failed tool call is remembered by its digest
The step SHALL record `argument_digest` of every tool call that ends as a retry or as a failure, with the reason that the log masked for it. It SHALL NOT record a call that returns a result.

#### Scenario: A retried call is remembered
- **WHEN** a tool call raises a retry error
- **THEN** the failed map of the `ToolCallLog` holds the digest that `argument_digest` gives for that call

#### Scenario: A repeated successful call runs
- **WHEN** the model sends again a call that returned a result
- **THEN** the tool handler runs again and the call returns its result with no refusal

### Requirement: An unchanged repeat of a failed call is refused
The executor SHALL refuse a tool call whose digest equals the digest of an earlier failed call of the same step, and SHALL return the earlier reason to the model as the result. The handler SHALL run once. A call whose digest differs SHALL run.

#### Scenario: An unchanged repeat gets the earlier reason
- **WHEN** the model sends the same failing call in two replies
- **THEN** the second call returns the refusal text with the earlier reason, and the tool handler has run once

#### Scenario: A changed argument runs
- **WHEN** the model changes one argument of the failed call
- **THEN** the tool handler runs and the call returns its result

#### Scenario: A path outside the checkout stays hidden
- **WHEN** the earlier retry names a path outside the checkout
- **THEN** the refusal text shows the text of `MESSAGES.roadmap.implement_tool_path_hidden` in place of that path

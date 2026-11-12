# roadmap-stage/replies Specification

## Purpose
How the stage job handles a model reply that breaks the schema or that a check refuses: the schema of the reply, the returns to the model, the logs, and the refused replies that the job keeps.

## Requirements

### Requirement: A reply that breaks the schema returns once
A reply of the proposal that fails the schema SHALL go back to the model once, with the field of each violation. A second reply that fails the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations.

#### Scenario: A valid second reply
- **WHEN** the first reply holds a group with an empty `changes` and the second reply is valid
- **THEN** the model gets two requests, the second names `groups[0].changes`, and the item is staged

#### Scenario: A second reply that fails
- **WHEN** both replies hold a blank `documentation`
- **THEN** the model gets two requests, and the item stops with the class `StructuredOutputValidationError`

### Requirement: A toolbox run keeps the return rules of a broken reply
A plan run of the toolbox SHALL send a reply that breaks the schema back to the model once, with the violations. A second reply that breaks the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations. A reply that the checks of the job refuse SHALL go back once, as it does without the toolbox.

#### Scenario: A reply that breaks the schema twice
- **WHEN** both replies of a plan run hold a group with an empty `changes`
- **THEN** the item stops with the class `StructuredOutputValidationError`

#### Scenario: A missing path after the tools
- **WHEN** the first plan of a toolbox run names a path that the commit lacks
- **THEN** the job asks again with the problem, and a second plan with a missing path stops the item

### Requirement: The stage reply has no return path
The reply schema of the stage job SHALL hold no key `premise_failed`, and SHALL require the keys `summary`, `pull_request_body`, `why`, `what_changes`, `skip_specs`, `feasibility`, `existing_tool` and `groups`. A reply that breaks the schema SHALL go back to the model once, and a second such reply SHALL fail the item with no change to its Status and no comment. No reply of the model SHALL return an item to New. The job itself returns an item to New only where another requirement says so.

#### Scenario: A reply with only premise_failed
- **WHEN** a reply is `{"premise_failed": "x"}`
- **THEN** the schema refuses it and names the key `premise_failed` as unknown

#### Scenario: A filler value of premise_failed
- **WHEN** a reply sets `premise_failed` to each of `placeholder`, `x`, `none`, `probe`, `__PROBE__` and "Not yet: I need to inspect the repository first." and holds a valid plan
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A premise text that states the premise holds
- **WHEN** a reply sets `premise_failed` to the text of #3193, #3109 or #3255, and #3109 quotes a probe line
- **THEN** the schema refuses each reply, and the job does not return the item

#### Scenario: A reply with no plan
- **WHEN** a reply is `{}`
- **THEN** the schema refuses it and names each missing key

#### Scenario: The job returns no item
- **WHEN** the job plans an item and the model answers with a refused reply twice
- **THEN** the item fails, its Status is unchanged, and the job writes no comment on it

### Requirement: A reference reason may be null
The schema of a reference in the reply of the stage job SHALL accept `null` or a string as `reason`. A reference with `unchanged` true SHALL have a reason that is a non-blank string, and the schema SHALL refuse `null` there. The prompt of the stage job SHALL give `reason` the value that the schema accepts when `unchanged` is false.

#### Scenario: A changed reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` false and `reason` null
- **THEN** the reply passes the schema

#### Scenario: An unchanged reference with a null reason
- **WHEN** a reply holds a reference with `unchanged` true and `reason` null
- **THEN** the schema refuses the reply and names the path of the reference

#### Scenario: A reply built from the prompt
- **WHEN** a reply holds a reference with `unchanged` false and the `reason` that the prompt states for that case
- **THEN** the reply passes the schema

### Requirement: A reply cut by the output token limit names the limit
A plan run or a review run of the stage job whose last model reply ends with the finish reason `length` SHALL fail with a `RoadmapStageError` that names the output token limit and `max_tokens`. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan reply cut by the limit
- **WHEN** the model of a plan run answers with the finish reason `length` and no part
- **THEN** the run raises a `RoadmapStageError` whose message names the output token limit and `max_tokens`
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review reply cut by the limit
- **WHEN** the model of a review run answers with the finish reason `length` and no part
- **THEN** the run raises the same error

#### Scenario: A stop that the limit did not cause
- **WHEN** a run ends because the reply broke the schema, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by the output token limit

### Requirement: A tool call with invalid arguments names the cause
A plan run or a review run of the stage job that ends because a tool call of its last model reply holds arguments that are not valid JSON SHALL fail with a `RoadmapStageError` that names the tool call with invalid arguments. The failure SHALL NOT be a schema failure, and the record of the failed item SHALL NOT show a count of schema violations for it.

#### Scenario: A plan call with joined arguments
- **WHEN** the last reply of a plan run holds a call to a tool with arguments of two JSON objects joined in one text
- **THEN** the run raises a `RoadmapStageError` whose message names a tool call with invalid arguments
- **AND** the error is not a `StructuredOutputValidationError`

#### Scenario: A review call with invalid arguments
- **WHEN** the last reply of a review run holds a call with arguments that are not valid JSON
- **THEN** the run raises the same error

#### Scenario: A stop that invalid arguments did not cause
- **WHEN** a run ends because the reply broke the schema with valid JSON, or because a budget limit was spent
- **THEN** the stop is not marked as a stop by invalid arguments

### Requirement: A refused reply is logged
The stage job SHALL log one line `stage reply refused` for each reply of the model that it refuses, with the number of the item, the number of the last request of the plan run, the input of that request in tokens, whether that request offered a function tool, the number of tool calls of the run, the limit that ended its tools, the stop reason and the model name of the last reply, and the result `refused` or `degenerate`. A fact that the run does not hold SHALL be written as `none`.

#### Scenario: A reply that the gates refuse
- **WHEN** the gates refuse the reply of item 1 in the second request of a plan run, and that request offered a tool
- **THEN** the log holds one line with `item=#1`, `request=2`, the input of the request in tokens, `tools_offered=True` and `result=refused`

#### Scenario: A degenerate reply that a provider stopped at its length
- **WHEN** the reply of item 1 is a placeholder in every text, after one tool call, and its stop reason is `length` and its model name is `fallback-model`
- **THEN** the log holds one line with `tool_calls=1`, `limit=none`, `finish_reason=length`, `answered=fallback-model` and `result=degenerate`

#### Scenario: A plan with no run
- **WHEN** the gates refuse a kept plan that no toolbox run made
- **THEN** the log holds one line with `tool_calls=0`, `limit=none`, `finish_reason=none` and `answered=none`

### Requirement: A failed item keeps its refused replies
When a plan fails, the stage job SHALL write the refused replies and their problems to the file `<n>.refused.json` beside the plan file of item `<n>`, under the key of the plan input. A new failed plan SHALL replace the file, and the staging of the item SHALL delete it. A reply over the byte bound SHALL be dropped with its size kept, and a problem SHALL be masked for secrets and cut to the character bound.

#### Scenario: The gates refuse a plan twice
- **WHEN** the gates refuse the first reply of item 1 and the reply after each return
- **THEN** the file `1.refused.json` holds the key and each reply, each with its problem, and no plan file exists

#### Scenario: The item is staged
- **WHEN** a later round stages item 1
- **THEN** the file `1.refused.json` is deleted

### Requirement: A reply of placeholders ends the item
The stage job SHALL end an item at once, with no second request, when a reply is a placeholder in `why`, `existing_tool`, each line of `feasibility` and each task of each group. The item SHALL fail with the error `RoadmapStageDegenerateError`, the job SHALL keep the reply as a refused reply, and `devops_cli_roadmap_stage_total` SHALL count the item under the result `degenerate`. A reply with one text that is no placeholder SHALL go back to the model as a refused reply.

#### Scenario: The first reply is all placeholders
- **WHEN** the first reply of item 1 holds `x` or `placeholder` in every text of the plan
- **THEN** the model gets one request, the item fails with `RoadmapStageDegenerateError`, and the result of the item is `degenerate`

#### Scenario: A reply with one real text
- **WHEN** the first reply holds `x` in `why` and in `feasibility` and a real text in `existing_tool`
- **THEN** the reply goes back to the model, as for any refused reply, and the result stays `failed` if the reply after the last return is refused

### Requirement: A schema failure names its violations
A plan run of the stage job whose model reply breaks the schema past its retries SHALL fail with an error whose failure line and log line name the count of violations, the stop reason (`validation` or `no tool call`) and at most 3 violations, each with its location, its pydantic error type and its message. Each text SHALL be masked for secrets and cut to 200 characters. The text SHALL NOT hold the input value of a violation.

#### Scenario: Two violations
- **WHEN** a plan reply breaks the schema with two violations, one at `references.0.reason`
- **THEN** the failure text holds `references.0.reason`, its error type, the stop reason and the count 2

#### Scenario: Five violations
- **WHEN** a plan reply breaks the schema with 5 violations
- **THEN** the failure text names 3 of them and the count 5

#### Scenario: A long message
- **WHEN** a violation message has 300 characters
- **THEN** the text holds the first 200 characters of it

#### Scenario: A secret in a message
- **WHEN** a violation message holds a token-shaped secret
- **THEN** the failure text, the log line and the kept file hold the masked value

### Requirement: A schema failure is kept in the refused file
When a plan fails because its reply broke the schema, the stage job SHALL write the stop reason, the count and the texts of the first violations in the field `schema_failure` of the file `<n>.refused.json`, with the replies that the checks refused before it. The staging of the item SHALL delete the file.

#### Scenario: A schema failure
- **WHEN** the plan of item 1 fails with two violations
- **THEN** the file `1.refused.json` holds the stop reason, the count 2 and both violations with their location, type and message

#### Scenario: The item stages later
- **WHEN** the item stages after a schema failure
- **THEN** the file `1.refused.json` is deleted

### Requirement: A failed model call names its reason
The stage job SHALL name the reason of an item that fails with `AIClientError`: the error code with the HTTP status or the timeout, then the message of the error with each quoted part hidden. It SHALL log one warning line `stage model call failed` with the number of the item, the class of the error, its code, its HTTP status and whether it timed out, and no text of the message. The reason SHALL NOT hold the text that a provider quotes from the model.

#### Scenario: A gateway error
- **WHEN** the model call of item 1 fails with `AIClientError("gateway returned 502", status=502)`
- **THEN** the failure of item 1 has the error `AIClientError`, and its reason holds `HTTP 502` and `gateway returned 502`, and the log holds one line with `item=#1` and `status=502`

#### Scenario: A provider that quotes the model
- **WHEN** the message of the error is `Ollama returned HTTP 500. Response: 'the reply of the model'`
- **THEN** the reason holds `Ollama returned HTTP 500` and does not hold `the reply of the model`

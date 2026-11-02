## ADDED Requirements

### Requirement: A step records its model calls and its tool calls
When the job gives a step a trace, the step SHALL add one event for each model call, with the model name, the input and output tokens and the seconds, and one event for each tool call, with the tool, the program, the digest of its masked argument and the outcome `ok`, `refused`, `retry` or `failed`. A retry SHALL hold the reason that the Job log shows.

#### Scenario: Two model calls
- **WHEN** a step ends after two model replies of 100 and 120 input tokens
- **THEN** the trace holds two `model` events with those input tokens, the model name and a number of seconds from the time of each request and its reply

#### Scenario: A refused command and a retried edit
- **WHEN** the model runs a command that the shell policy refuses, and an `edit_file` whose `old_text` is missing
- **THEN** the trace holds a `tool` event with the outcome `refused` and the program, and a `tool` event with the outcome `retry` and the reason of the tool

#### Scenario: The digest of an argument
- **WHEN** the model makes the same call twice and a third call with another command
- **THEN** the first two events hold the same digest of 12 hexadecimal characters, the third holds another, and no event holds the command

### Requirement: A step records its checks and its retries
The step SHALL add one event for each command that it runs as an exit check, with the command and its exit status, and one event for each repair round and each send again of a model request, with the reason.

#### Scenario: A failed lint and one repair round
- **WHEN** `ruff check` exits 1 on the files of a step, a repair round fixes them, and the check exits 0
- **THEN** the trace holds a `check` event with exit status 1, a `retry` event with the reason, and a `check` event with exit status 0, in that order

#### Scenario: A command that runs out of time
- **WHEN** a check command exceeds the command timeout
- **THEN** the `check` event holds no exit status and says that it timed out

### Requirement: Every text of an event is masked
The step SHALL pass each text of an event through `bounded_text` and `mask_private_hosts` and escape it to one line, and SHALL build the digest from the argument with each secret-named value hidden. An event SHALL hold no secret and no private host name.

#### Scenario: A secret and a host in a reason
- **WHEN** the reason of a retry holds `Bearer abcdefghijklmnopqrstuvwxyz0123` and `db.corp.internal`
- **THEN** the event holds `<masked-token>` and `<masked-host>`, and neither original text

#### Scenario: A secret-named argument
- **WHEN** two calls differ only in the value of the argument `api_key`
- **THEN** their events hold the same digest and neither value

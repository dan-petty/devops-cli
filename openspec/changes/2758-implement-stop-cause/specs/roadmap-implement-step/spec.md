# Spec Delta

## MODIFIED Requirements

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` model requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls, and the extra turn for the ticks SHALL count against them. A run that reaches a limit, or breaks the rules of its tools past their retries, SHALL end as stopped with a reason that holds the class name and the message of the pydantic-ai error. The step SHALL mask secrets in the message with `mask_secrets`, then cut it to `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters, and SHALL reset the checkout. The agent SHALL have no `delegate_task` tool.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Tool 'shell' exceeded max retries count of 5.`, and the checkout is reset

#### Scenario: A secret in the message of the error
- **WHEN** the message of the pydantic-ai error holds a token in the form of a GitHub token
- **THEN** the reason holds the mask in place of the token

#### Scenario: A long message of the error
- **WHEN** the message of the pydantic-ai error is longer than `CONST_ROADMAP_IMPLEMENT_ERROR_CHARS` characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

## ADDED Requirements

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count, over all its turns, the tool calls that a tool refused by its policy and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when either is not zero. A call counts as refused when a `PermissionError` is in the `__cause__` chain of the retry, and the step SHALL read no message text to tell the two apart.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `CONST_ROADMAP_IMPLEMENT_TOOL_RETRIES` times
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and the shell allows only `git`, `uv`, `ruff` and `mypy`
- **THEN** the reason ends with "Refused commands: 6. Other retries: 0."

#### Scenario: Arguments that fail validation
- **WHEN** the model calls the tool `read_file` without its `path` argument in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A run with no retry
- **WHEN** the model calls `read_file` with a valid path in every reply until the request limit
- **THEN** the reason holds the message of the error and holds neither count

### Requirement: Every tool call of a step writes one line to the Job log
The agent of a step SHALL write one line to the standard error stream for each tool call. The line SHALL hold the name of the tool, the first word of the `command` argument when the tool has one, and the outcome: `ok`, `refused`, `retry` or `failed`. The line SHALL hold no other argument, no file content, no output and no text of a refusal.

#### Scenario: A refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py --secret-flag=abc`, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: shell, program pytest, refused." and holds no text of the arguments

#### Scenario: A call that returns
- **WHEN** the model calls `write_file` with a path and a content, and then ends its run
- **THEN** the standard error stream holds the line "Tool call: write_file, ok." and holds neither the path nor the content

#### Scenario: A call that fails validation
- **WHEN** the model calls `read_file` without its `path` argument
- **THEN** the standard error stream holds the line "Tool call: read_file, retry."

#### Scenario: A secret as the first word
- **WHEN** the model calls the shell tool with a command whose first word is a token in the form of a GitHub token
- **THEN** the line holds the mask in place of the token

#### Scenario: A long first word
- **WHEN** the first word of a shell command is longer than `CONST_ROADMAP_IMPLEMENT_PROGRAM_CHARS` characters
- **THEN** the line holds the word cut to that length

#### Scenario: A call that the tool reports as failed
- **WHEN** a tool reports a failed call
- **THEN** the standard error stream holds the line "Tool call: <tool>, failed."

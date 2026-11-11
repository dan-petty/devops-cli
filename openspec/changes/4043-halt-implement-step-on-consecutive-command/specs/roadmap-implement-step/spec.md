## ADDED Requirements

### Requirement: Consecutive refusals stop the step
The implement step SHALL end the run as stopped when the shell policy refuses `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` commands in a row, and the checkout SHALL reset. Any tool call that is not refused SHALL reset the count to 0. The stop SHALL use the failure class `refused_tool`. The constant `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` SHALL be 3.

#### Scenario: Three refusals in a row
- **WHEN** the shell policy refuses 3 commands in a row and no tool call is accepted between them
- **THEN** the third refusal ends the run, the reason names the limit of 3, the failure class is `refused_tool`, and the checkout is reset

#### Scenario: Refusals split by an accepted call
- **WHEN** the shell policy refuses 2 commands, a tool call is accepted, and the shell policy refuses 2 more commands
- **THEN** the step does not stop for the consecutive limit

## MODIFIED Requirements

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, exceeds the retries of a tool, has more than `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` shell refusals in the step, or has `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` shell refusals in a row, SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`, and no `delegate_task`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the model gets `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` minus one refusals as tool results, the next refusal ends the run, the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Too many consecutive commands refused by policy: the limit is` and the limit, and the checkout is reset

#### Scenario: A model that alternates a refused and an accepted call
- **WHEN** the model calls a refused command and an accepted tool in every reply
- **THEN** the model gets `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` refusals as tool results, the next call ends the run, and the reason starts with `UnexpectedModelBehavior: Too many commands refused by policy in one step: the limit is` and the limit

#### Scenario: The stop of the refusal limit is a refused tool
- **WHEN** the step stops because the shell refused more commands than the limit
- **THEN** the failure class of the reason is `refused_tool`

#### Scenario: A secret in the message of the error
- **WHEN** the message of the pydantic-ai error holds a token in the form of a GitHub token
- **THEN** the reason holds the mask in place of the token

#### Scenario: A long message of the error
- **WHEN** the message of the pydantic-ai error is longer than `CONST_ROADMAP_RUN_ERROR_CHARS` characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

#### Scenario: The body of the error
- **WHEN** the pydantic-ai error has the message `The reply broke the rules.` and the body `MODEL-TEXT`
- **THEN** the reason is `UnexpectedModelBehavior: The reply broke the rules.`, with no `MODEL-TEXT`

### Requirement: The reason of a stopped run counts the refused and the retried tool calls
A step that stops on a pydantic-ai error SHALL count the tool calls that a tool refused by its policy, by program, and the tool calls that came back as a retry for another cause. The reason SHALL end with both counts when a count is not zero. It SHALL list at most `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS` programs, most refused first, and join the rest to `other`. A call counts as refused when the shell refused its command or an argument by its policy.

#### Scenario: The call that exceeds the limit
- **WHEN** the model is refused more often than `CONST_ROADMAP_IMPLEMENT_MAX_REFUSALS` times, or `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS` times in a row
- **THEN** the call that ends the run counts as refused too

#### Scenario: Refused commands
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply, and `pytest` is not a program of the shell table
- **THEN** the reason ends with a new line and "Refused commands: pytest 3. Other retries: 0.", where 3 is `CONST_ROADMAP_IMPLEMENT_MAX_CONSECUTIVE_REFUSALS`

#### Scenario: Refused commands of two programs
- **WHEN** the model is refused `python` four times and `cd` twice, and then another error ends the run
- **THEN** the reason ends with "Refused commands: python 4, cd 2."

#### Scenario: Refused commands of many programs
- **WHEN** the model is refused more distinct programs than `CONST_ROADMAP_IMPLEMENT_REFUSED_PROGRAMS`
- **THEN** the reason lists that number of programs and the count of `other` holds the rest

#### Scenario: Arguments that fail validation
- **WHEN** the model calls the tool `read_file` without its `path` argument in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A path outside the root
- **WHEN** the model calls `read_file` with the path `/etc/passwd` in every reply
- **THEN** the reason ends with "Refused commands: 0. Other retries: 6."

#### Scenario: A run with no retry
- **WHEN** the model calls `read_file` with a valid path in every reply until the request limit
- **THEN** the reason holds the message of the error and holds neither count

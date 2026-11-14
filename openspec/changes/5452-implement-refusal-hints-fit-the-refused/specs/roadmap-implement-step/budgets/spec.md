## MODIFIED Requirements

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `roadmap.implement.max_requests` requests and `roadmap.implement.max_tool_calls` tool calls. A run that reaches a limit, exceeds the retries of a tool, or exceeds a limit of shell refusals (total or in a row), SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with UsageLimitExceeded: and holds the message of the error, the model got roadmap.implement.max_requests requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than roadmap.implement.max_tool_calls before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with UsageLimitExceeded: , and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `create_directory`, `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`, and no `delegate_task`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with UsageLimitExceeded: , and the model got roadmap.implement.max_requests requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with pytest sample in every reply
- **THEN** the model gets roadmap.implement.max_consecutive_refusals minus one refusals as tool results, the next refusal ends the run, the step reports stopped with a reason that starts with UnexpectedModelBehavior: Too many consecutive commands refused by policy: the limit is and the limit, and the checkout is reset

#### Scenario: A model that alternates a refused and an accepted call
- **WHEN** the model calls a refused command and an accepted tool in every reply
- **THEN** the model gets roadmap.implement.max_refusals refusals as tool results, the next call ends the run, and the reason starts with UnexpectedModelBehavior: Too many commands refused by policy in one step: the limit is and the limit

#### Scenario: The stop of the refusal limit is a refused tool
- **WHEN** the step stops because the shell refused more commands than the limit
- **THEN** the failure class of the reason is refused_tool

#### Scenario: A secret in the message of the error
- **WHEN** the message of the pydantic-ai error holds a token in the form of a GitHub token
- **THEN** the reason holds the mask in place of the token

#### Scenario: A long message of the error
- **WHEN** the message of the pydantic-ai error is longer than CONST_ROADMAP_RUN_ERROR_CHARS characters
- **THEN** the message in the reason is cut to that length, and the counts of the next requirement are still in the reason

#### Scenario: The body of the error
- **WHEN** the pydantic-ai error has the message The reply broke the rules. and the body MODEL-TEXT
- **THEN** the reason is UnexpectedModelBehavior: The reply broke the rules., with no MODEL-TEXT

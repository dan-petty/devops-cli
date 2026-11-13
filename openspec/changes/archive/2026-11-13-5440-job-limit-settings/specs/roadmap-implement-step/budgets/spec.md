## ADDED Requirements

### Requirement: The limits that end an implement step are settings
The implement step SHALL read each limit that ends its run from `roadmap.implement` when the step starts. The default of each new setting SHALL be the value of the constant that it replaces, so a step with no configuration does not change. The file tools of the harness SHALL take `tool_retries` in place of their own count.

#### Scenario: No configuration
- **WHEN** no source sets `max_requests`, `max_tool_calls`, `tool_retries`, `max_refusals`, `max_consecutive_refusals`, `model_resends`, `extension_calls` and `extension_max_refused`
- **THEN** they are 500, 1500, 5, 30, 3, 1, 20 and 3, the values of the constants that they replace

#### Scenario: The refusal and retry limits of a setting
- **WHEN** `max_consecutive_refusals` is 5, `max_refusals` is 7 and `tool_retries` is 2
- **THEN** 5 refusals in a row stop a step, 7 refusals between accepted calls stop a step at its eighth request, and a third failure of `read_file` in a row stops a step

#### Scenario: No resend and a small request limit
- **WHEN** `model_resends` is 0 and `max_requests` is 2
- **THEN** a request that fails with a 400 inside a stream is not sent again, and a model that reads in every reply gets 2 requests

#### Scenario: The window of the extension
- **WHEN** `extension_calls` is 10 and `extension_max_refused` is 5
- **THEN** the digest of the tool log counts the last 10 calls, and a step at its token budget with 5 refused commands in them gets the extension

### Requirement: An implement limit has a ceiling and an order
The settings load SHALL refuse a value of an implement limit above 4 times its default (`CONST_ROADMAP_LIMIT_CEILING_FACTOR`) with an error that names the setting. It SHALL refuse `max_consecutive_refusals` above `max_refusals`, and `extension_max_refused` above `extension_calls`, with an error that names both settings.

#### Scenario: A value above the ceiling
- **WHEN** `roadmap.implement.max_refusals` is 121
- **THEN** the settings load fails with an error that names `roadmap.implement.max_refusals`

#### Scenario: Refusals in a row above the total
- **WHEN** `max_refusals` is 2 and `max_consecutive_refusals` keeps its default of 3
- **THEN** the settings load fails with the error `max_consecutive_refusals must not be above max_refusals`

## MODIFIED Requirements

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `roadmap.implement.max_requests` requests and `roadmap.implement.max_tool_calls` tool calls. A run that reaches a limit, exceeds the retries of a tool, or exceeds a limit of shell refusals (total or in a row), SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

#### Scenario: A model that never ends
- **WHEN** the model calls a tool in every reply
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: ` and holds the message of the error, the model got `roadmap.implement.max_requests` requests at most, and the checkout is reset

#### Scenario: A model that calls too many tools
- **WHEN** the model calls more tools than `roadmap.implement.max_tool_calls` before it reaches the request limit
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the checkout is reset

#### Scenario: The tools of the agent
- **WHEN** the step makes its first request
- **THEN** the function tools offered are `edit_file`, `grep`, `list_files`, `read_file`, `run_command` and `write_file`, and no `delegate_task`

#### Scenario: The extra turn shares the budget
- **WHEN** the first turn used all but one of the model requests and the extra turn needs two
- **THEN** the step reports stopped with a reason that starts with `UsageLimitExceeded: `, and the model got `roadmap.implement.max_requests` requests at most over both turns

#### Scenario: A model that keeps calling a refused program
- **WHEN** the model calls the shell tool with `pytest tests/test_sample.py` in every reply
- **THEN** the model gets `roadmap.implement.max_consecutive_refusals` minus one refusals as tool results, the next refusal ends the run, the step reports stopped with a reason that starts with `UnexpectedModelBehavior: Too many consecutive commands refused by policy: the limit is` and the limit, and the checkout is reset

#### Scenario: A model that alternates a refused and an accepted call
- **WHEN** the model calls a refused command and an accepted tool in every reply
- **THEN** the model gets `roadmap.implement.max_refusals` refusals as tool results, the next call ends the run, and the reason starts with `UnexpectedModelBehavior: Too many commands refused by policy in one step: the limit is` and the limit

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

### Requirement: A step that makes progress gets one extension of its token budget
When a step reaches `roadmap.implement.step_token_budget` and no other budget is spent, the step SHALL read the digest of its last `extension_calls` tool calls (default 20) in its tool log. With at least 1 successful edit and at most `extension_max_refused` refused commands (default 3), the step SHALL raise its token budget one time by 50 percent, up to `step_token_ceiling`, and go on. The rule is the only resolver of the decision point `implement.extension`, and no decision model takes part.

#### Scenario: The shapes of pilot 3 that a person finished
- **WHEN** a step reaches a budget of 50 tokens with the counts (successful edits, refused commands) of one of the 16 stops of pilot 3 that a person finished later, from (1, 3) to (10, 0)
- **THEN** the budget is not spent, and the extension holds a budget of 75 tokens and those counts

#### Scenario: The ceiling cuts the extension
- **WHEN** `step_token_budget` is 50, `step_token_ceiling` is 60 and the step makes progress at its budget
- **THEN** the extension holds a budget of 60 tokens and says that the ceiling cut it

### Requirement: The digest of progress holds counts of the tool log
The digest SHALL count, in the last `roadmap.implement.extension_calls` tool calls of the step (default 20) over all its turns and tiers, the successful edits (a `write_file` or an `edit_file` call with the outcome ok) and the refused commands (a call with the outcome refused). A log with fewer tool calls than that SHALL give no digest. The digest SHALL hold counts only.

#### Scenario: The counts of the last calls
- **WHEN** the log holds 21 calls: an `edit_file` with the outcome ok, 15 reads, a `write_file` with the outcome ok, an `edit_file` with the outcome retry, a `write_file` that failed and 2 refused shell calls
- **THEN** the digest holds 20 calls, 1 successful edit and 2 refused commands, because the first edit is out of the window

#### Scenario: A short log
- **WHEN** the log holds 19 calls
- **THEN** the log gives no digest

### Requirement: A step with no progress at its token budget stops as before
The step SHALL stop with the class `limit_reached` at its token budget, and SHALL name `roadmap.implement.step_token_budget` and its value, when its tool log gives no digest, when the digest holds no successful edit or more than `roadmap.implement.extension_max_refused` refused commands (default 3), when the ceiling leaves no room above the tokens already used, or when the step already used its extension. A step SHALL decide one time at each limit.

#### Scenario: The shapes of pilot 3 that repeated refused commands
- **WHEN** a step reaches a budget of 50 tokens with the counts (0, 11), (1, 10), (0, 16), (1, 4) or (0, 9)
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_budget=50` and the counts in its last 20 tool calls

#### Scenario: A step that repeats refused commands
- **WHEN** `step_token_budget` is 50 and the first reply makes 20 tool calls with 4 refused commands and no edit
- **THEN** the model gets no second request, the step stops with the class `limit_reached`, and the outcome holds no extension

#### Scenario: The item budget holds
- **WHEN** a step got its extension and then reaches `item_token_budget` before the end of the extension
- **THEN** the step stops with the class `limit_reached`, and the reason names `roadmap.implement.item_token_budget`

### Requirement: The reason of a stop at the token budget names its cause
The reason of a stop at the token budget SHALL give the counts of the digest, say that the log holds fewer tool calls than `roadmap.implement.extension_calls` (default 20), name the ceiling and its value, or name the new budget of the extension.

#### Scenario: A short log at the budget
- **WHEN** a step reaches its budget after 3 tool calls
- **THEN** the step stops with the class `limit_reached`, and the reason says that the log holds fewer than 20 tool calls

#### Scenario: The second limit
- **WHEN** an extended step reaches its new budget of 75 tokens
- **THEN** the step stops with the class `limit_reached`, and the reason names `roadmap.implement.step_token_budget=50` and the extension to 75 new tokens

#### Scenario: The ceiling ends the extension
- **WHEN** the ceiling of 60 tokens cut the extension and the step reaches 60 tokens
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_ceiling=60`

#### Scenario: The ceiling leaves no room
- **WHEN** `step_token_ceiling` is equal to `step_token_budget` and the step makes progress at its budget
- **THEN** the step stops, and the reason names `roadmap.implement.step_token_ceiling` and its value

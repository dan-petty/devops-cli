# roadmap-implement-step/budgets Specification

## Purpose
The budgets and the time limits of an implement step and of an item: the settings, the stop at a budget, and the extension of a token budget for a step that makes progress.

## Requirements

### Requirement: A run that reaches a limit ends stopped
`UsageLimits` SHALL cap a run, extra turn included, at `CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS` requests and `CONST_ROADMAP_IMPLEMENT_MAX_TOOL_CALLS` tool calls. A run that reaches a limit, exceeds the retries of a tool, or exceeds a limit of shell refusals (total or in a row), SHALL end as stopped, and the step SHALL reset the checkout. The reason SHALL hold the class and the `message` of the error, masked and cut to `CONST_ROADMAP_RUN_ERROR_CHARS` characters.

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

### Requirement: The time limits of the implement job are settings
The settings `roadmap.implement.request_timeout_seconds`, `roadmap.implement.command_timeout_seconds` and `roadmap.implement.monitor_timeout_seconds` SHALL set the seconds that a model call, a command and the watch of the checks of a pull request may take. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 1200, 1800 and 3600, and a value below 1 SHALL be refused. A reader SHALL ask for the value when it runs.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a time limit
- **THEN** the call deadline is 1200 seconds, the command limit is 1800 seconds and the watch limit is 3600 seconds

#### Scenario: A config file and a variable
- **WHEN** the config file sets `command_timeout_seconds` to 90 and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS` holds 120
- **THEN** the command limit is 90 and the watch limit is 120

#### Scenario: A limit of zero
- **WHEN** the config file sets a time limit to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: A model call
- **WHEN** the config file sets `request_timeout_seconds` to 77 and a step makes its first model request
- **THEN** the model settings of the request hold `request_timeout` 77

#### Scenario: A scoped check
- **WHEN** the config file sets `command_timeout_seconds` to 41 and the job runs the scoped checks
- **THEN** each command runs with the limit 41, and a command that runs out of time fails its check with a reason that names 41 seconds

#### Scenario: The watch of the checks
- **WHEN** the config file sets `monitor_timeout_seconds` to 123 and the checks of the pull request are still pending
- **THEN** the watch waits at most 123 seconds, and the reason of the stop names 123 seconds

### Requirement: The budgets of a step and of an item are settings
The settings `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` and `item_time_limit_seconds` SHALL set the new tokens and the seconds that a step and a run of an item may use. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 8000000, 20000000, 5400 and 12600.

A value below 1 SHALL be refused. An item time limit above `roadmap.implement.deadline_ceiling_seconds` SHALL be refused too.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a budget
- **THEN** the step budget is 8000000 tokens, the item budget is 20000000 tokens, the step limit is 5400 seconds and the item limit is 12600 seconds

#### Scenario: A variable
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET` holds 5000
- **THEN** the step budget is 5000

#### Scenario: A budget of zero
- **WHEN** the config file sets `step_token_budget` to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: An item limit above the ceiling of the Job
- **WHEN** the config file sets `item_time_limit_seconds` above `deadline_ceiling_seconds`
- **THEN** loading the settings fails and the message names `item_time_limit_seconds`

### Requirement: A step that spends a budget stops and names it
Before each model request, the step SHALL compare its new tokens and its seconds with the budgets of the step and of the item. When one is spent, the step SHALL make no request, stop with the class `limit_reached` and name the setting and its value, unless the rule `implement.extension` extends the token budget of the step. The item budget SHALL count the tokens of the earlier steps, and the item limit the seconds since the run began. The step SHALL reset the checkout as for any stop.

#### Scenario: The token budget of the step
- **WHEN** `step_token_budget` is 50, the first reply of the model reports more than 50 new tokens, and the step made fewer than 20 tool calls
- **THEN** the step reports stopped with the class `limit_reached`, the model got no second request, and the reason names `roadmap.implement.step_token_budget` and 50

#### Scenario: The token budget of the item
- **WHEN** the earlier steps of the run used 900 new tokens and `item_token_budget` is 1000
- **THEN** a step stops after its first reply, and the reason names `roadmap.implement.item_token_budget` and 1000

#### Scenario: The time limit of the step
- **WHEN** `step_time_limit_seconds` is 60 and the clock shows 61 seconds since the step began
- **THEN** the step makes no further request, stops with the class `limit_reached`, and the reason names `roadmap.implement.step_time_limit_seconds` and 60

#### Scenario: The time limit of the item
- **WHEN** the run began 100 seconds ago and `item_time_limit_seconds` is 60
- **THEN** the step makes no request and the reason names `roadmap.implement.item_time_limit_seconds` and 60

#### Scenario: Within the budgets
- **WHEN** a step uses less than every budget
- **THEN** the step is not stopped for a budget

#### Scenario: A repair turn
- **WHEN** the first turn used the whole time limit of the step and a check fails
- **THEN** the repair turn makes no request and the step stops with the class `limit_reached`

### Requirement: The stop of the repair rounds names the setting
When a step stops with a failure that a repair round could have taken, and all the rounds are used, the reason SHALL end with a line that names `roadmap.implement.repair_rounds` and its value.

#### Scenario: The rounds are used
- **WHEN** `ruff check` still exits 1 after every round and `repair_rounds` is 2
- **THEN** the reason names `ruff check` and then holds a line with `roadmap.implement.repair_rounds=2`

#### Scenario: A failure with no round
- **WHEN** a verification command exits 1, which gets no repair round
- **THEN** the reason holds no line about the repair rounds

### Requirement: The ceiling of a step budget is a setting
The setting `roadmap.implement.step_token_ceiling` SHALL set the most tokens, in the unit of `step_token_budget`, that a step may reach with its one extension. It SHALL have the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`. When no config file and no variable sets it, the ceiling SHALL be twice the loaded `step_token_budget`, also after a change of the budget, and the settings SHALL not store it. A ceiling below `roadmap.implement.step_token_budget` SHALL be refused.

#### Scenario: The default ceiling
- **WHEN** no config file and no variable sets the ceiling or the step budget
- **THEN** the ceiling is twice the default step budget

#### Scenario: A step budget above the old fixed ceiling
- **WHEN** the config file sets `step_token_budget` to 17000000 and sets no ceiling
- **THEN** the settings load and the ceiling is 34000000

#### Scenario: A variable for the step budget only
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET` holds 17000000 and nothing sets the ceiling
- **THEN** the settings load and the ceiling is 34000000

#### Scenario: The whole extension
- **WHEN** `step_token_budget` is 12000000, nothing sets the ceiling, and the step makes progress at its budget
- **THEN** the extension holds a budget of 18000000 tokens and says that the ceiling did not cut it

#### Scenario: A change of the step budget by `devops config set`
- **WHEN** nothing sets the ceiling and `devops config set roadmap.implement.step_token_budget 20000000` runs
- **THEN** the command exits 0, the config file gets the budget and no ceiling, and the ceiling is 40000000

#### Scenario: A variable for the ceiling
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` holds 9000000
- **THEN** the ceiling is 9000000

#### Scenario: A ceiling below the step budget
- **WHEN** the config file sets `step_token_budget` to 5000 and `step_token_ceiling` to 4999
- **THEN** loading the settings fails and the message names `step_token_ceiling`

### Requirement: A step that makes progress gets one extension of its token budget
When a step reaches `roadmap.implement.step_token_budget` and no other budget is spent, the step SHALL read the digest of its last 20 tool calls from its tool log. With at least 1 successful edit and at most 3 refused commands, the step SHALL raise its token budget one time by 50 percent of the budget, up to `roadmap.implement.step_token_ceiling`, and go on. The rule is the only resolver of the decision point `implement.extension`, and no decision model takes part.

#### Scenario: The shapes of pilot 3 that a person finished
- **WHEN** a step reaches a budget of 50 tokens with the counts (successful edits, refused commands) of one of the 16 stops of pilot 3 that a person finished later, from (1, 3) to (10, 0)
- **THEN** the budget is not spent, and the extension holds a budget of 75 tokens and those counts

#### Scenario: The ceiling cuts the extension
- **WHEN** `step_token_budget` is 50, `step_token_ceiling` is 60 and the step makes progress at its budget
- **THEN** the extension holds a budget of 60 tokens and says that the ceiling cut it

### Requirement: The digest of progress holds counts of the tool log
The digest SHALL count, in the last 20 tool calls of the step over all its turns and tiers, the successful edits (a `write_file` or an `edit_file` call with the outcome ok) and the refused commands (a call with the outcome refused). A log with fewer than 20 tool calls SHALL give no digest. The digest SHALL hold counts only.

#### Scenario: The counts of the last calls
- **WHEN** the log holds 21 calls: an `edit_file` with the outcome ok, 15 reads, a `write_file` with the outcome ok, an `edit_file` with the outcome retry, a `write_file` that failed and 2 refused shell calls
- **THEN** the digest holds 20 calls, 1 successful edit and 2 refused commands, because the first edit is out of the window

#### Scenario: A short log
- **WHEN** the log holds 19 calls
- **THEN** the log gives no digest

### Requirement: The Job log and the outcome show the extension
The step SHALL write one line to the Job log that names the rule `implement.extension`, the old and the new budget, and the counts. The outcome of the step SHALL hold the extension: the old budget, the new budget, the counts and whether the ceiling cut it.

#### Scenario: A step that edits at its budget
- **WHEN** `step_token_budget` is 250 and the first reply makes 20 tool calls with 3 successful edits and counts 280 new tokens
- **THEN** the model gets a second request, the step ends done, and the Job log names the extension from 250 to 375 new tokens with 3 successful edits and 0 refused commands

### Requirement: A step with no progress at its token budget stops as before
The step SHALL stop with the class `limit_reached` at its token budget, and SHALL name `roadmap.implement.step_token_budget` and its value, when its tool log gives no digest, when the digest holds no successful edit or more than 3 refused commands, when the ceiling leaves no room above the tokens already used, or when the step already used its extension. A step SHALL decide one time at each limit.

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
The reason of a stop at the token budget SHALL give the counts of the digest, say that the log holds fewer than 20 tool calls, name the ceiling and its value, or name the new budget of the extension.

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

### Requirement: The decisions of the extension are counted
Each decision of the rule `implement.extension` SHALL add 1 to `devops_cli_roadmap_implement_extension_total` with the label `decision`, `extended` or `halted`, and 0 to the other value, so the metric has 2 series. A step SHALL count at most two decisions: one extension and one stop.

#### Scenario: An extension
- **WHEN** the rule extends the budget of a step
- **THEN** the counter gets 1 for `extended` and 0 for `halted`

#### Scenario: A stop that the step asks again
- **WHEN** a halted step checks its budget again
- **THEN** the counter gets no second count

### Requirement: A token budget counts the new tokens of a reply
The step budget, its ceiling and the item budget SHALL count the new tokens of each reply: the input tokens that the provider did not read from its cache, and the output tokens. The outcome of a step and the record `implement.spend` SHALL keep the cached input tokens, and the record SHALL keep the count of the item budget as `new_tokens`. The item budget SHALL count the `new_tokens` of the earlier Jobs of the item, and none for a record that has no `new_tokens`.

#### Scenario: The count of one reply
- **WHEN** a reply reports 120000 input tokens, 118500 of them read from the cache, and 300 output tokens
- **THEN** the budget counts 1800 tokens

#### Scenario: Cached input does not stop a step
- **WHEN** `step_token_budget` is 500 and each of the two replies of a step reports 100000 more input tokens, all read from the cache
- **THEN** the step is not stopped for a budget, the model gets two requests, and the outcome holds 200000 cached input tokens

#### Scenario: The cached input of an earlier Job
- **WHEN** `item_token_budget` is 1000 and the record of an earlier Job holds 100100 input tokens, 100000 of them read from the cache, and 100 `new_tokens`
- **THEN** the next Job is not stopped for the item budget, and its record still holds the 100000 cached input tokens

#### Scenario: A record that names no unit
- **WHEN** `item_token_budget` is 1000 and the record of an earlier Job, as an older version wrote it, holds 100100 input tokens and no `new_tokens`
- **THEN** the next Job is not stopped for the item budget, its record keeps the 100100 input tokens, and its `new_tokens` are the new tokens of the next Job only

#### Scenario: A route that reports no cache reads
- **WHEN** no setting changes the step budget and each reply reports 39300 input tokens, none of them read from the cache, and 200 output tokens
- **THEN** the step makes at least 200 requests before its token budget, as when the budget counted all input tokens

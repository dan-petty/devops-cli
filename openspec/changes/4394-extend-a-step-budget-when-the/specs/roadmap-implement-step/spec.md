## MODIFIED Requirements

### Requirement: The budgets of a step and of an item are settings
The settings `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` and `item_time_limit_seconds` SHALL set the input tokens and the seconds that a step and a run of an item may use. The setting `roadmap.implement.step_token_ceiling` SHALL set the most input tokens that a step may reach with its one extension. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 8000000, 20000000, 5400, 12600 and 16000000.

A value below 1 SHALL be refused. An item time limit above `roadmap.implement.deadline_ceiling_seconds` SHALL be refused too, and so SHALL a ceiling below `step_token_budget`.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a budget
- **THEN** the step budget is 8000000 tokens, the item budget is 20000000 tokens, the step limit is 5400 seconds, the item limit is 12600 seconds and the ceiling is 16000000 tokens

#### Scenario: A variable
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_BUDGET` holds 5000
- **THEN** the step budget is 5000

#### Scenario: A budget of zero
- **WHEN** the config file sets `step_token_budget` to 0
- **THEN** loading the settings fails and the message names the setting

#### Scenario: An item limit above the ceiling of the Job
- **WHEN** the config file sets `item_time_limit_seconds` above `deadline_ceiling_seconds`
- **THEN** loading the settings fails and the message names `item_time_limit_seconds`

#### Scenario: A ceiling below the step budget
- **WHEN** the config file sets `step_token_budget` to 5000 and `step_token_ceiling` to 4999
- **THEN** loading the settings fails and the message names `step_token_ceiling`

### Requirement: A step that spends a budget stops and names it
Before each model request, the step SHALL compare the input tokens of the replies so far, and the seconds since it began, with the budgets of the step and of the item. When one is spent, the step SHALL make no request, stop with the class `limit_reached`, and write a reason that names the setting and its value. The one exception is the token budget of the step, which the rule `implement.extension` can extend one time. The tokens of earlier steps of the run SHALL count for the item budget, and the seconds since the run began for the item limit. The step SHALL reset the checkout as for any stop.

#### Scenario: The token budget of the step
- **WHEN** `step_token_budget` is 50, the first reply of the model reports more than 50 input tokens, and the step made fewer than 20 tool calls
- **THEN** the step reports stopped with the class `limit_reached`, the model got no second request, and the reason names `roadmap.implement.step_token_budget` and 50

#### Scenario: The token budget of the item
- **WHEN** the earlier steps of the run used 900 input tokens and `item_token_budget` is 1000
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

## ADDED Requirements

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
- **WHEN** `step_token_budget` is 50 and the first reply makes 20 tool calls with 3 successful edits
- **THEN** the model gets a second request, the step ends done, and the Job log names the extension from 50 to 75 input tokens with 3 successful edits and 0 refused commands

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
- **THEN** the step stops with the class `limit_reached`, and the reason names `roadmap.implement.step_token_budget=50` and the extension to 75 input tokens

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

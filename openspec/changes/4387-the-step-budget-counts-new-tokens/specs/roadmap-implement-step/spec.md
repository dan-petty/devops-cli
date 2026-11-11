## ADDED Requirements

### Requirement: A token budget counts the new tokens of a reply
The step budget, its ceiling and the item budget SHALL count the new tokens of each reply: the input tokens that the provider did not read from its cache, and the output tokens. The outcome of a step and the record `implement.spend` SHALL keep the input tokens that the provider read from its cache, and the item budget SHALL count the new tokens of the earlier Jobs of the item.

#### Scenario: The count of one reply
- **WHEN** a reply reports 120000 input tokens, 118500 of them read from the cache, and 300 output tokens
- **THEN** the budget counts 1800 tokens

#### Scenario: Cached input does not stop a step
- **WHEN** `step_token_budget` is 500 and each of the two replies of a step reports 100000 more input tokens, all read from the cache
- **THEN** the step is not stopped for a budget, the model gets two requests, and the outcome holds 200000 cached input tokens

#### Scenario: The cached input of an earlier Job
- **WHEN** `item_token_budget` is 1000 and the record of an earlier Job holds 100100 input tokens, 100000 of them read from the cache
- **THEN** the next Job is not stopped for the item budget, and its record still holds the 100000 cached input tokens

## MODIFIED Requirements

### Requirement: The budgets of a step and of an item are settings
The settings `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` and `item_time_limit_seconds` SHALL set the new tokens and the seconds that a step and a run of an item may use. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 1000000, 2500000, 5400 and 12600.

A value below 1 SHALL be refused. An item time limit above `roadmap.implement.deadline_ceiling_seconds` SHALL be refused too.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a budget
- **THEN** the step budget is 1000000 tokens, the item budget is 2500000 tokens, the step limit is 5400 seconds and the item limit is 12600 seconds

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

### Requirement: The ceiling of a step budget is a setting
The setting `roadmap.implement.step_token_ceiling` SHALL set the most new tokens that a step may reach with its one extension. It SHALL have the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`. Its default SHALL be 2000000, twice the default step budget. A ceiling below `roadmap.implement.step_token_budget` SHALL be refused.

#### Scenario: The default ceiling
- **WHEN** no config file and no variable sets the ceiling
- **THEN** the ceiling is 2000000 tokens

#### Scenario: A variable for the ceiling
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` holds 9000000
- **THEN** the ceiling is 9000000

#### Scenario: A ceiling below the step budget
- **WHEN** the config file sets `step_token_budget` to 5000 and `step_token_ceiling` to 4999
- **THEN** loading the settings fails and the message names `step_token_ceiling`

### Requirement: The Job log and the outcome show the extension
The step SHALL write one line to the Job log that names the rule `implement.extension`, the old and the new budget, and the counts. The outcome of the step SHALL hold the extension: the old budget, the new budget, the counts and whether the ceiling cut it.

#### Scenario: A step that edits at its budget
- **WHEN** `step_token_budget` is 250 and the first reply makes 20 tool calls with 3 successful edits and counts 280 new tokens
- **THEN** the model gets a second request, the step ends done, and the Job log names the extension from 250 to 375 new tokens with 3 successful edits and 0 refused commands

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

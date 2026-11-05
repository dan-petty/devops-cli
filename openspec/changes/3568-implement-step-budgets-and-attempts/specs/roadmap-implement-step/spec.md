## ADDED Requirements

### Requirement: The budgets of a step and of an item are settings
The settings `roadmap.implement.step_token_budget`, `item_token_budget`, `step_time_limit_seconds` and `item_time_limit_seconds` SHALL set the input tokens and the seconds that a step and a run of an item may use. Each SHALL have a variable named `DEVOPS_CLI_` and the key in upper case. The defaults SHALL be 8000000, 20000000, 5400 and 12600.

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
Before each model request, the step SHALL compare the input tokens of the replies so far, and the seconds since it began, with the budgets of the step and of the item. When one is spent, the step SHALL make no request, stop with the class `limit_reached`, and write a reason that names the setting and its value. The tokens of earlier steps of the run SHALL count for the item budget, and the seconds since the run began for the item limit. The step SHALL reset the checkout as for any stop.

#### Scenario: The token budget of the step
- **WHEN** `step_token_budget` is 50 and the first reply of the model reports more than 50 input tokens
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

### Requirement: The stop of the repair rounds names the setting
When a step stops with a failure that a repair round could have taken, and all the rounds are used, the reason SHALL end with a line that names `roadmap.implement.repair_rounds` and its value.

#### Scenario: The rounds are used
- **WHEN** `ruff check` still exits 1 after every round and `repair_rounds` is 2
- **THEN** the reason names `ruff check` and then holds a line with `roadmap.implement.repair_rounds=2`

#### Scenario: A failure with no round
- **WHEN** a verification command exits 1, which gets no repair round
- **THEN** the reason holds no line about the repair rounds

### Requirement: A failure that no attempt can fix gets no repair round
A failure of the class `plan_defect` or `premise_false` SHALL get no repair round, whatever the setting `repair_rounds` is. The step SHALL stop with the evidence of the failure. Only a failed static check or hook, and a missing tick, get a round.

#### Scenario: A group that changes no file
- **WHEN** the model ends its run and changes no file of a group
- **THEN** the step reports stopped with the class `plan_defect`, the model got one run and no extra turn, and the trace holds one attempt

### Requirement: A step records each attempt
The step SHALL add one `attempt` event to the trace for the first run and for each repair round. The event SHALL hold the number of the attempt, the tier, the outcome `passed` or `failed`, the failure class of a failed attempt, its evidence, and `repair` or `stop` for what follows. The evidence SHALL pass the masking of every text of an event.

#### Scenario: A failing check that passes on the second attempt
- **WHEN** `ruff check` exits 1 after the first run, and the model fixes the file in the repair round
- **THEN** the trace holds two `attempt` events: attempt 1 failed with class `lint` and the evidence of `ruff`, followed by `repair`, and attempt 2 passed

#### Scenario: A stop
- **WHEN** the repair rounds are used and the check still fails
- **THEN** the last `attempt` event is failed and followed by `stop`

#### Scenario: A fatal class
- **WHEN** the group changes no file
- **THEN** the trace holds one `attempt` event, failed with class `plan_defect` and followed by `stop`

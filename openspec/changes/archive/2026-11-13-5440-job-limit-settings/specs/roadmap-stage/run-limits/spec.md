## ADDED Requirements

### Requirement: The limits that end a stage attempt are settings
The stage job SHALL read each limit that ends an attempt from `roadmap.stage` when a round starts. The default of each new setting SHALL be the value of the constant that it replaces, so a run with no configuration does not change.

#### Scenario: No configuration
- **WHEN** no source sets `gate_return_extensions`, `verify_repair_rounds_ceiling`, `plan_defect_limit`, `max_requests`, `max_tool_calls`, `plan_calls_advised`, `plan_calls_notice`, `review_calls_advised` and `review_calls_notice`
- **THEN** they are 1, 4, 3, 250, 200, 30, 40, 40 and 60, the values of the constants that they replace

#### Scenario: The call limit of a run
- **WHEN** `roadmap.stage.max_tool_calls` is 5 and one reply of a plan run holds 6 tool calls
- **THEN** the item fails, and the reason names `tool_calls_limit`

### Requirement: A stage limit has a ceiling and an order
The settings load SHALL refuse a value of a stage limit above 4 times its default (`CONST_ROADMAP_LIMIT_CEILING_FACTOR`) with an error that names the setting. It SHALL refuse an advice above its notice, and a notice above `max_tool_calls`, with an error that names both settings.

#### Scenario: A value above the ceiling
- **WHEN** `roadmap.stage.plan_defect_limit` is 13
- **THEN** the settings load fails with an error that names `roadmap.stage.plan_defect_limit`

#### Scenario: A notice above the tool calls
- **WHEN** `roadmap.stage.max_tool_calls` is 50 and the notices keep their defaults
- **THEN** the settings load fails with the error `review_calls_notice must not be above max_tool_calls`

#### Scenario: The doubled values
- **WHEN** each new setting is twice its default and `roadmap.stage.gate_returns` is 6
- **THEN** the settings load gives these values

## MODIFIED Requirements

### Requirement: A plan run has a budget
A plan run of the toolbox SHALL make at most `roadmap.stage.max_tool_calls` tool calls and `roadmap.stage.max_requests` model requests. It SHALL set no count of output tokens: the context window ends the tools of a run. The run SHALL offer no tool to a request when fewer than 4 tool calls are left, so the model gives its plan. A run that passes a limit SHALL fail the item with a reason. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

#### Scenario: The tool call limit
- **WHEN** one reply of the model in a plan run holds one more parallel tool call than `roadmap.stage.max_tool_calls`
- **THEN** the item fails, and the reason names `tool_calls_limit`

#### Scenario: The tools are gone near the limit
- **WHEN** the model has made `roadmap.stage.max_tool_calls` minus 3 tool calls, one in each turn
- **THEN** the next request offers no tool, and a valid plan in the reply stages the item

#### Scenario: The output token limit
- **WHEN** the replies of the model in one plan run hold more than 50000 output tokens, and the last reply is a valid plan
- **THEN** the item is staged

#### Scenario: A run inside the budget
- **WHEN** the model reads two files and then answers with a valid plan
- **THEN** the item is staged

#### Scenario: One item fails and the others are planned
- **WHEN** the plan run of the first of two items spends its budget
- **THEN** the second item is planned, and the job fails at the end for the first item

### Requirement: The budget is for each plan run
A plan run SHALL be one model call for a plan. The budget of a plan run SHALL be for that run, not for the item. The planner can make a second plan run for one item, when the checks of the job refuse the first plan. That second run SHALL start with a new budget, so one item can use twice `roadmap.stage.max_tool_calls` tool calls at most. The model call that splits the groups of an item SHALL use no tool and SHALL have no tool budget.

#### Scenario: The budget is for each plan run
- **WHEN** the first plan run of an item makes 20 tool calls, the checks refuse its plan, and the second plan run makes 20 tool calls
- **THEN** the second run is inside its own budget, and the item is staged

### Requirement: A plan run measures its calls and the limit that ended its tools
A plan run that ends with a plan or a stop SHALL observe `devops_cli_roadmap_tool_calls_per_run` once, with its count of tool calls and the labels `row` and `toolset`. A run that raises because a model call failed SHALL observe no count of calls. A run that ends its tools on a limit SHALL add 1, once, to `devops_cli_roadmap_tool_limit_hits_total` with the labels `row`, `toolset` and `limit`. The `limit` SHALL be `calls`, `requests` or `window`.

#### Scenario: The three limits
- **WHEN** a plan run ends its tools because fewer calls are left than a turn needs, because one request is left, or because the messages fill the context window
- **THEN** the limit counter holds one point with `limit` `calls`, `requests` or `window` in that order

#### Scenario: A run stops at the call limit
- **WHEN** a plan run makes calls until the request that offers no tool because the call budget is spent
- **THEN** the histogram observes one run, and the limit counter holds one point with `limit` `calls`

#### Scenario: A run fills the context window
- **WHEN** a plan run reads a large file in each turn, with a context window of 12000 tokens
- **THEN** the limit counter holds one point with `limit` `window`

#### Scenario: One reply over the call limit
- **WHEN** one reply of the model holds one more parallel tool call than `roadmap.stage.max_tool_calls`
- **THEN** the run fails, and the limit counter holds one point with `limit` `calls`

#### Scenario: A run whose model call fails
- **WHEN** the first call of a plan run is a tool call, and its second model request fails
- **THEN** the counter of calls holds the first call, and the histogram of calls per run holds no observation

### Requirement: A review run that stops names itself
When a verification run ends with no reply, the failure of the item SHALL name the verification run and SHALL NOT say that no plan was given.

#### Scenario: A verification run hits a limit
- **WHEN** the replies of a verification run pass `roadmap.stage.max_tool_calls`
- **THEN** the job raises `RoadmapStageError` with the message of a stopped verification run

### Requirement: A run has a call budget
From call `roadmap.stage.plan_calls_notice` of a stage plan run, and from call `roadmap.stage.review_calls_notice` of a review run, the answer of each tool SHALL end with a notice that names the call number and tells the model to read no more and give its reply. The tools SHALL stay on, and each run SHALL start its count at zero.

#### Scenario: A plan run past its budget
- **WHEN** a plan run makes three calls and the budget of a plan run is 2
- **THEN** the answer of the first call has no notice, and the answers of the second and third calls end with the notice

#### Scenario: A review run
- **WHEN** a review run makes three calls, the budget of a plan run is 1 and the budget of a review run is 3
- **THEN** only the answer of the third call ends with the notice

#### Scenario: A new run
- **WHEN** a second run starts after a run that passed its budget
- **THEN** the first answers of the second run have no notice

### Requirement: The prompts of a run name its call budget
The prompt of a stage plan run SHALL say that a plan needs about `roadmap.stage.plan_calls_advised` tool calls, and the prompt of a review run SHALL say that a review needs about `roadmap.stage.review_calls_advised`. Each prompt SHALL name the call from which the answers carry the notice. The prompt of a plan run SHALL say that a request with `problem` needs a tool call only to check what the problem names.

#### Scenario: The prompts
- **WHEN** the prompts of the plan run and the review run are read
- **THEN** they name the advised calls and the call of the notice that the settings hold, and no placeholder stays

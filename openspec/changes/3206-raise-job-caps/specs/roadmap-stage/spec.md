# Spec Delta

## MODIFIED Requirements

### Requirement: The job measures each task group
The job SHALL measure each task group with tiktoken: the tokens of the group's instructions, the item, the change folder, the `AGENTS.md` of the repository, the routed sections of its documents, and the files that the tasks of the group name in code spans, each packed as the implement step packs it, at most `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens. The budget SHALL be `roadmap.stage.step_tokens`, default half of the default window of the implement task (64000 tokens), and `--step-tokens` SHALL override it for one run.

#### Scenario: A group is measured
- **WHEN** the model gives a group whose task names a file of the repository
- **THEN** the comment on the issue gives the group's measure, and that measure is more than the tokens of the file packed

#### Scenario: A large file counts as the step reads it
- **WHEN** a task of a group names one file that holds more tokens than the budget
- **THEN** the group measure is under the budget, and the job asks the model for no split

#### Scenario: A file that no task names
- **WHEN** the `Reads:` line of a group lists a file that no task of the group names
- **THEN** the file adds no token to the measure, as the step does not read it

#### Scenario: The rules count
- **WHEN** the repository holds an `AGENTS.md` and a group names `tests/test_sample.py`
- **THEN** the measure of the group holds the tokens of the `AGENTS.md` and of the routed sections of `docs/TESTING.md`

### Requirement: The settings name the filter, the limit and the step budget
The settings `roadmap.stage.filter`, `roadmap.stage.limit` and `roadmap.stage.step_tokens` SHALL set what the stage job takes. Each SHALL have the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER`, `DEVOPS_CLI_ROADMAP_STAGE_LIMIT` or `DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS`. The defaults SHALL be the filter `status=ready`, the limit 3 and the step budget 64000, half of the default window of the implement task. The example ConfigMap of the Service SHALL hold the default filter.

#### Scenario: The defaults
- **WHEN** no config file and no variable sets a `roadmap.stage` setting
- **THEN** the filter, the limit and the step budget are the defaults above

#### Scenario: A config file and a variable
- **WHEN** the config file sets `roadmap.stage.limit` to 1 and the variable `DEVOPS_CLI_ROADMAP_STAGE_FILTER` holds `status=ready,type=feature`
- **THEN** the limit is 1 and the filter is `status=ready` and `type=feature`

#### Scenario: A round uses the settings
- **WHEN** the filter is `type=feature` and the limit is 1, and the roadmap holds two Ready features and a Ready bug
- **THEN** a round of the `stage` row plans the first feature only

#### Scenario: The example ConfigMap
- **WHEN** the example ConfigMap of the Service is rendered and loaded as settings
- **THEN** its stage filter equals the default filter

### Requirement: A plan run has a budget
A plan run of the toolbox SHALL make at most `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls and `CONST_ROADMAP_STAGE_MAX_REQUESTS` model requests. It SHALL set no count of output tokens, because the tokens of its replies are in its messages and the context window ends the tools of a run. The run SHALL offer no tool to a request when fewer than 4 tool calls are left, so the model gives its plan. A run that passes a limit SHALL fail the item with a reason. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

#### Scenario: The tool call limit
- **WHEN** one reply of the model in a plan run holds one more parallel tool call than `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the item fails, and the reason names `tool_calls_limit`

#### Scenario: The tools are gone near the limit
- **WHEN** the model has made `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` minus 3 tool calls, one in each turn
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

### Requirement: A plan run keeps its messages inside the context window
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `analysis` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

### Requirement: The tools read a checkout that is the staged commit
The toolbox SHALL refuse a checkout whose HEAD is not the staged commit, or that has a change that is not committed or a file that git does not track, before any model call. The failure SHALL be a `RoadmapStageError`. A tool SHALL read the size of a file before it reads the file, SHALL refuse a file of more than 2000000 bytes, and SHALL number only the lines that it returns. `search_code` and `callers` SHALL stop at one more than `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` matches in one file.

#### Scenario: A modified file
- **WHEN** the checkout holds a modified tracked file
- **THEN** building the toolbox raises `RoadmapStageError` and the model gets no request

#### Scenario: A file over the size limit
- **WHEN** `read_file` gets a file of more than 2000000 bytes
- **THEN** it answers that the file is too large to read

#### Scenario: A file with many matches
- **WHEN** a file holds three times `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines that match `callers`
- **THEN** the answer holds `CONST_ROADMAP_REFINE_TOOL_MAX_LINES` lines and says that lines are left out

### Requirement: The map and the spec tools give short answers
`repo_map` SHALL give one line for each of at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files, with the path and the names of the top-level symbols, cut to 180 characters. It SHALL end with a line that says so when the directory holds more files. `read_spec` SHALL read the capabilities, the requirement names and the requirement text from the JSON of `openspec list --specs` and `openspec show --type spec`. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

### Requirement: A call to a tool that is gone gets a retry
When a request offers no tool, a call of the model to a function tool SHALL get a retry prompt, and the run SHALL go on. The run SHALL fail the item when the model calls a gone tool a third time, because the tool retry limit is 2. The reason of the failure SHALL name the retry limit, and no budget limit. It holds no tool name, because the name of a tool in an error message is text that the model chose.

#### Scenario: One call after the tools are gone
- **WHEN** the model has made `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` minus 3 tool calls, calls `read_file` once in a request that offers no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Two calls after the tools are gone
- **WHEN** the model calls `read_file` twice in requests that offer no tool, and then gives a valid plan
- **THEN** the item is staged

#### Scenario: Three calls after the tools are gone
- **WHEN** the model calls `read_file` a third time in requests that offer no tool
- **THEN** the item fails, and the reason names the retry limit 2, and no budget limit

### Requirement: The budget is for each plan run
A plan run SHALL be one model call for a plan. The budget of a plan run SHALL be for that run, not for the item. The planner can make a second plan run for one item, when the checks of the job refuse the first plan. That second run SHALL start with a new budget, so one item can use twice `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls at most. The model call that splits the groups of an item SHALL use no tool and SHALL have no tool budget.

#### Scenario: The budget is for each plan run
- **WHEN** the first plan run of an item makes 20 tool calls, the checks refuse its plan, and the second plan run makes 20 tool calls
- **THEN** the second run is inside its own budget, and the item is staged

## ADDED Requirements

### Requirement: A plan run counts each tool call by outcome
A plan run of the toolbox SHALL add 1 to `devops_cli_roadmap_tool_calls_total` for each tool call of the toolset. The labels SHALL be `tool`, `row` (`stage`), `toolset` (`base` or `extended`) and `outcome` (`ok`, `empty` or `error`). A call that no tool answers SHALL count as `error`.

#### Scenario: One call of each outcome
- **WHEN** a plan run calls `read_file` for a file with text, calls `search_code` for a text that no file holds, and calls `read_file` for a path outside the repository
- **THEN** the counter holds one point for each of the outcomes `ok`, `empty` and `error`, and each point has the labels `tool`, `row` `stage` and `toolset`

#### Scenario: A call that no tool answers
- **WHEN** a tool call is rejected, the run no longer offers the tool, or a limit stops the call
- **THEN** the call counts with `outcome` `error`

#### Scenario: A tool that the toolset does not offer
- **WHEN** the model calls a name that is no tool of the toolset
- **THEN** the counter holds no point with that name as `tool`

### Requirement: The tool that answers a call sets its outcome
Each tool of the stage planner SHALL set the `outcome` of its answer: `ok` for the result that the call asked for, `empty` for a call that ran and found nothing, and `error` for a call that could not run. A tool that sets no outcome SHALL give `ok`, or `empty` for an answer with no non-whitespace character.

#### Scenario: Each tool sets its own outcome
- **WHEN** a test calls each tool of the toolset `extended` that can find nothing with an argument that finds nothing, and each tool that can refuse with an argument that it refuses
- **THEN** the answer of each first call has the outcome `empty` and the answer of each second call has the outcome `error`

#### Scenario: A tool that sets no outcome
- **WHEN** a tool of a run answers with text, and a tool answers with white space only, and neither sets an outcome
- **THEN** the first call counts as `ok` and the second as `empty`

### Requirement: A plan run measures the size of each answer
A plan run SHALL observe `devops_cli_roadmap_tool_answer_chars` once for each tool call that got an answer, with the labels `tool`, `row` and `toolset`. The value SHALL be the count of characters of the answer after the cut of the tool. A call with no answer SHALL add no observation. The text of an answer with the outcome `error` is an answer.

#### Scenario: A long answer is cut
- **WHEN** a plan run reads a file of 300 long lines and the tool cuts the answer
- **THEN** the histogram observes the length of the cut answer that the model read, and not the length of the file

### Requirement: Each plan run gives every tool of its toolset a series
A plan run SHALL add 0 to `devops_cli_roadmap_tool_calls_total` with `outcome` `ok` for each tool of its toolset, before its first model request.

#### Scenario: A run that calls no tool
- **WHEN** a plan run with the toolset `base` makes no tool call
- **THEN** the counter holds nine points with the value 0 and `outcome` `ok`, one for each tool

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
- **WHEN** one reply of the model holds one more parallel tool call than `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the run fails, and the limit counter holds one point with `limit` `calls`

#### Scenario: A run whose model call fails
- **WHEN** the first call of a plan run is a tool call, and its second model request fails
- **THEN** the counter of calls holds the first call, and the histogram of calls per run holds no observation

### Requirement: The comment of a staged item counts the calls of each tool
The comment of an item that the toolbox planned SHALL add one line after the list of tool calls. The line SHALL name each tool that the plan runs called, in alphabetical order, with its count of calls and its count of empty answers, as `Tool calls: read_file=3 (empty=0), search_code=2 (empty=1)`. The comment SHALL hold no such line when the plan runs made no tool call.

#### Scenario: Two tools and one empty answer
- **WHEN** a plan run calls `read_file` twice and `search_code` once for a text that no file holds
- **THEN** the comment holds the line `Tool calls: read_file=2 (empty=0), search_code=1 (empty=1)`

#### Scenario: An item with two plan runs
- **WHEN** the first plan of an item is refused and each of the two plan runs calls `read_file` once
- **THEN** the line of the comment holds `read_file=2 (empty=0)`

#### Scenario: A run that made no tool call
- **WHEN** a plan run makes no tool call
- **THEN** the comment holds no line that starts with `Tool calls:`

### Requirement: A git command that runs out of time is an error
A tool of the stage planner whose git command runs out of time SHALL answer with the outcome `error` and a text that says so. It SHALL NOT answer that nothing was found.

#### Scenario: Each tool that runs git
- **WHEN** every git command of `search_code`, `list_files`, `read_file`, `git_log`, `git_show`, `callers` and `references` runs out of time
- **THEN** each answer has the outcome `error`, and its text says that the command ran out of time

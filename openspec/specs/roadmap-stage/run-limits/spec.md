# roadmap-stage/run-limits Specification

## Purpose
The limits of a plan run and their measures: the budget, the call budget and the context window of each request, the trace of the tools that a request offered, and the metrics of the tool calls.

## Requirements

### Requirement: A plan run has a budget
A plan run of the toolbox SHALL make at most `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls and `CONST_ROADMAP_STAGE_MAX_REQUESTS` model requests. It SHALL set no count of output tokens: the context window ends the tools of a run. The run SHALL offer no tool to a request when fewer than 4 tool calls are left, so the model gives its plan. A run that passes a limit SHALL fail the item with a reason. The job SHALL plan the other items, and SHALL open no draft pull request for the failed item.

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
A plan run SHALL offer no tool to a request when the tokens of its messages, with a quarter of the context window of the `stage` task, reach the window. The model SHALL then give its plan. The tool answers SHALL NOT make a request longer than the window by more than the reply that was kept free. The run SHALL take the tokens of its messages from the usage of the last reply, plus the text after it, with no fixed factor.

#### Scenario: A model that reads a big file in every turn
- **WHEN** a plan run has a window of 12000 tokens and the model reads a file of 120 long lines in every turn
- **THEN** a request offers no tool before the budget of tool calls, no request passes the window, and the plan stages the item

#### Scenario: A run with no window
- **WHEN** a run is given no window
- **THEN** only the budget of tool calls takes the tools away

#### Scenario: The count follows the reported input
- **WHEN** the last reply of a run reports an input of 105,412 tokens and the window is 200000
- **THEN** the count of the messages is within 10 percent of 105,412 tokens and the next request offers its tools

#### Scenario: The reported input has no room for a reply
- **WHEN** the last reply reports an input of 149,900 tokens and the window is 200000
- **THEN** the next request offers no tool

#### Scenario: The text after the last reply counts
- **WHEN** the last reply reports 140,000 tokens and the answer after it holds more than 10,000 tokens of text
- **THEN** the next request offers no tool

#### Scenario: The first request
- **WHEN** the run has no reply yet
- **THEN** its count is the count of the instructions and the user prompt, within 2 percent

#### Scenario: A reply that reports no input
- **WHEN** a provider omits the input tokens of its replies
- **THEN** the count of the messages is the count of their text, within 2 percent, and not the count of their JSON form

#### Scenario: A call to a tool that is not offered
- **WHEN** the model calls `read_file` while only `final_result` is offered
- **THEN** the return names `final_result` as the tool that is available

### Requirement: The budget is for each plan run
A plan run SHALL be one model call for a plan. The budget of a plan run SHALL be for that run, not for the item. The planner can make a second plan run for one item, when the checks of the job refuse the first plan. That second run SHALL start with a new budget, so one item can use twice `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS` tool calls at most. The model call that splits the groups of an item SHALL use no tool and SHALL have no tool budget.

#### Scenario: The budget is for each plan run
- **WHEN** the first plan run of an item makes 20 tool calls, the checks refuse its plan, and the second plan run makes 20 tool calls
- **THEN** the second run is inside its own budget, and the item is staged

### Requirement: The comment of a staged item reports the plan run
The comment of an item that the toolbox planned SHALL report all plan runs of the item, in the order they ran. It SHALL list each tool call with the name and the masked, cut argument of the call. It SHALL state the count of model requests, the input tokens and the output tokens, summed over all plan runs of the item. The comment of an item planned without the toolbox SHALL hold none of these lines.

#### Scenario: The comment lists the calls
- **WHEN** the model calls `read_file` for `src/devops_cli/sample.py` and then answers
- **THEN** the comment of the staged item lists `read_file` with that path and the token counts

#### Scenario: An item with two plan runs
- **WHEN** the first plan of an item is refused, and the second plan run makes one tool call
- **THEN** the comment lists the tool calls of both runs in order, and its token counts are the sums of both runs

#### Scenario: An argument with a secret
- **WHEN** a tool call has an argument that looks like a secret
- **THEN** the comment holds the masked text and not the secret

### Requirement: The first plan request has fixed caps and leaves a reserve for the tools
The first request of a plan run SHALL cap the context at `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body at `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, and a larger window SHALL NOT give a larger cap. Half of the window for the context, or one quarter for the body, SHALL cap it when that is less. For plain text, the request at the caps SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the limit at which the run offers no tool.

#### Scenario: The context and the body at their caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens, the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens, the first request counts at most the limit of 49152 tokens less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`, and the first request offers `read_spec`

#### Scenario: Code at the caps
- **WHEN** a plan run has a window of 65536 tokens, and the context and the body of the item are code, longer than their caps
- **THEN** the first request counts less than the limit of 49152 tokens, and the first request offers `read_spec`

#### Scenario: A large window
- **WHEN** a plan run has a window of 1048576 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens and the body counts `CONST_ROADMAP_STAGE_BODY_MAX_TOKENS` tokens

#### Scenario: A small window
- **WHEN** a plan run has a window of 8192 tokens, and the context and the body of the item are longer than their caps
- **THEN** the context counts 4096 tokens and the body counts 2048 tokens

### Requirement: The context and the largest spec answer stay under half of the window
The context of the first plan request and the longest answer of `read_spec` SHALL together stay under half of the context window of the `analysis` task.

#### Scenario: The longest spec answer
- **WHEN** a test adds an answer of `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS` characters to a context of `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens
- **THEN** the sum is under 32768 tokens

### Requirement: The trace of a run records the tools that each request offered
`RunTrace` SHALL hold, for each model request of a run, the names of the function tools that the request offered, and an empty entry for a request that offered none. The combined trace of several runs SHALL hold the entries of every run in order.

#### Scenario: A run that loses its tools
- **WHEN** a scripted plan run reads a big file until the window limit takes the tools, and the model then gives its plan
- **THEN** the trace holds the tool names of the first request and an empty entry for the last request, and the entries equal the tools that the model saw

#### Scenario: Two runs
- **WHEN** `RunTrace.combined` gets two traces that hold one and two entries
- **THEN** the result holds the three entries in order

### Requirement: The window of the analysis task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `analysis` and the file that sets it, and the `max_input_tokens` of the model of that task and the file that sets it. The stated values SHALL equal the values in `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a test reads the two files and the page
- **THEN** the page states 256,000 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and `k8s/llm/gateway/config.yaml`, as the files hold them

### Requirement: The refine investigation request is measured against the tool-removal limit
A test SHALL build the first request of a refine investigation at a window of 65536 tokens, count its tokens as the run hook counts them, print the count with the limit of 49152 tokens, and assert that the request of a large item stays under the limit. Refine SHALL NOT change.

#### Scenario: A large item
- **WHEN** refine investigates an item with a body of 8192 tokens and three replies of 1000 tokens
- **THEN** the test prints the count and the limit, and the count is under 49152 tokens

### Requirement: The stage job plans with the model of the stage task
The stage command and the stage round of the Service SHALL give the planner the model of the task `stage` as its toolbox model, and the call that splits the groups SHALL use the client of the task `stage`.

#### Scenario: The command asks for the stage model
- **WHEN** `devops roadmap stage --plan` plans an item
- **THEN** the command asks for the model of the task `stage`, and the planner offers its tools to that model

#### Scenario: A round asks for the stage model
- **WHEN** a round of the Service plans an item
- **THEN** the round asks for the model of the task `stage`

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

### Requirement: The verification request fits the window of its task
The request and the run of the verifier SHALL use the context window of the task `verification`. With its instructions, the request SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the point where the run offers no more tools.

#### Scenario: A request that does not fit the window
- **WHEN** the cited files of a plan do not fit the limit of the window of the task `verification`
- **THEN** the request keeps the cited files in plan order up to that limit, and drops the others

#### Scenario: A full request gets the tools
- **WHEN** the window of the task `verification` is 65536 tokens and a plan cites more files than fit
- **THEN** the first request of the run is offered the read tools

#### Scenario: The two tasks have different windows
- **WHEN** the task `stage` has a window of 262144 tokens and the task `verification` a window of 12000 tokens
- **THEN** the request of the verifier and the tool limit of its run follow the window of 12000 tokens

### Requirement: A review run has its own row in the metrics of the tool calls
A verification run SHALL send the metrics of its tool calls with the label `row` value `stage_verify`, and a plan run SHALL keep the value `stage`, so the reads of the verifier do not hide a tool that the planner does not use.

#### Scenario: A verification run calls a tool
- **WHEN** a verification run reads a file
- **THEN** `devops_cli_roadmap_tool_calls_total` holds that call with `row` `stage_verify`, and no point with `row` `stage`

### Requirement: A review run that stops names itself
When a verification run ends with no reply, the failure of the item SHALL name the verification run and SHALL NOT say that no plan was given.

#### Scenario: A verification run hits a limit
- **WHEN** the replies of a verification run pass `CONST_ROADMAP_STAGE_TOOL_MAX_CALLS`
- **THEN** the job raises `RoadmapStageError` with the message of a stopped verification run

### Requirement: The comment states that the model chose no tool
The comment of a staged item whose plan runs made no tool call SHALL say on how many of the requests tools were offered, and that the model called none.

#### Scenario: A run that offered tools
- **WHEN** a plan run offers tools in its one request and the model gives its plan with no tool call
- **THEN** the comment says that the run offered tools on 1 of 1 request(s) and the model called none

### Requirement: A plan run whose window ends the tools too soon fails the item
When the context window ends the tools of a plan run or of a review run before the run made `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool calls, the run SHALL raise `RoadmapStageError`, whatever its reply is. The message SHALL name the window, the count of calls and the setting to raise. The job SHALL record that error for the item.

#### Scenario: The window ends the tools after one call
- **WHEN** a plan run has a window of 12000 tokens, reads a big file, and the window takes the tools after fewer calls than the least number
- **THEN** the run raises `RoadmapStageError` that names the window, `ai.tasks.stage.context_window` and the parent `ai.tasks.analysis.context_window`, though the model gave a valid plan

#### Scenario: The window ends the tools after the least number of calls
- **WHEN** a plan run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its plan
- **THEN** the run returns the plan

#### Scenario: A review run
- **WHEN** a review run has a window of 12000 tokens that ends its tools after fewer calls than the least number, and the model gives no finding
- **THEN** the run raises `RoadmapStageError` that names the window and `ai.tasks.verification.context_window`, and not `ai.tasks.stage.context_window`

#### Scenario: A review run whose window ends the tools after the least number of calls
- **WHEN** a review run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its findings
- **THEN** the run returns the findings

#### Scenario: The job records the window
- **WHEN** the stage job runs an item with a window of 8192 tokens, and the model answers a plan after one call
- **THEN** the item fails with `RoadmapStageError` and the reason names `ai.tasks.stage.context_window`

### Requirement: The planner window of the example ConfigMap fits a plan run
The context window of the task `analysis` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first plan request and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `analysis` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first request plus the tokens of the least number of long tool answers, and the window of 65536 tokens is below that point

### Requirement: The review window of the example ConfigMap fits a review run
The context window of the task `verification` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first review request with no cited file and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size. The task SHALL name its window, so it does not take the default window of the `ai` settings.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `verification` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first review request plus the tokens of the least number of long tool answers, and the default window of 32768 tokens is below that point

### Requirement: A run has a call budget
From call `CONST_ROADMAP_STAGE_PLAN_CALLS_NOTICE` of a stage plan run, and from call `CONST_ROADMAP_STAGE_REVIEW_CALLS_NOTICE` of a review run, the answer of each tool SHALL end with a notice that names the call number and tells the model to read no more and give its reply. The tools SHALL stay on, and each run SHALL start its count at zero.

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
The prompt of a stage plan run SHALL say that a plan needs about `CONST_ROADMAP_STAGE_PLAN_CALLS_ADVISED` tool calls, and the prompt of a review run SHALL say that a review needs about `CONST_ROADMAP_STAGE_REVIEW_CALLS_ADVISED`. Each prompt SHALL name the call from which the answers carry the notice. The prompt of a plan run SHALL say that a request with `problem` needs a tool call only to check what the problem names.

#### Scenario: The prompts
- **WHEN** the prompts of the plan run and the review run are read
- **THEN** they name the advised calls and the call of the notice that the constants hold

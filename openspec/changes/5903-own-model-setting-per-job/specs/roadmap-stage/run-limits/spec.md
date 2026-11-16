# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: The window of the analysis task is documented with its source`
- TO: `### Requirement: The window of the stage task is documented with its source`

## MODIFIED Requirements

### Requirement: The context and the largest spec answer stay under half of the window
The context of the first plan request and the longest answer of `read_spec` SHALL together stay under half of the context window of the `stage` task.

#### Scenario: The longest spec answer
- **WHEN** a test adds an answer of `CONST_ROADMAP_STAGE_SPEC_MAX_CHARS` characters to a context of `CONST_ROADMAP_STAGE_CONTEXT_MAX_TOKENS` tokens
- **THEN** the sum is under 32768 tokens

### Requirement: The window of the stage task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `stage` and the file that sets it, and the `max_input_tokens` of the model of that task and the file that sets it. The stated values SHALL equal the values in `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a test reads the two files and the page
- **THEN** the page states 256,000 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and `k8s/llm/gateway/config.yaml`, as the files hold them

### Requirement: The verification request fits the window of its task
The request and the run of the verifier SHALL use the context window of the task of the review: `stage_review` in the stage job and `fix_plan_review` in `fix-plan`. With its instructions, the request SHALL stay `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` tokens below the point where the run offers no more tools.

#### Scenario: A request that does not fit the window
- **WHEN** the cited files of a plan do not fit the limit of the window of the task `stage_review`
- **THEN** the request keeps the cited files in plan order up to that limit, and drops the others

#### Scenario: A full request gets the tools
- **WHEN** the window of the task `stage_review` is 65536 tokens and a plan cites more files than fit
- **THEN** the first request of the run is offered the read tools

#### Scenario: The two tasks have different windows
- **WHEN** the task `stage` has a window of 262144 tokens and the task `stage_review` a window of 12000 tokens
- **THEN** the request of the verifier and the tool limit of its run follow the window of 12000 tokens

### Requirement: A plan run whose window ends the tools too soon fails the item
When the context window ends the tools of a plan run or of a review run before the run made `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool calls, the run SHALL raise `RoadmapStageError`, whatever its reply is. The message SHALL name the window, the count of calls and the window setting of the task of the run, `ai.tasks.<task>.context_window`. The job SHALL record that error for the item.

#### Scenario: The window ends the tools after one call
- **WHEN** a plan run has a window of 12000 tokens, reads a big file, and the window takes the tools after fewer calls than the least number
- **THEN** the run raises `RoadmapStageError` that names the window and `ai.tasks.stage.context_window` and no setting of `ai.tasks.analysis`, though the model gave a valid plan

#### Scenario: The window ends the tools after the least number of calls
- **WHEN** a plan run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its plan
- **THEN** the run returns the plan

#### Scenario: A review run
- **WHEN** a review run has a window of 12000 tokens that ends its tools after fewer calls than the least number, and the model gives no finding
- **THEN** the run raises `RoadmapStageError` that names the window and `ai.tasks.stage_review.context_window`, and not `ai.tasks.stage.context_window`

#### Scenario: A review run whose window ends the tools after the least number of calls
- **WHEN** a review run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its findings
- **THEN** the run returns the findings

#### Scenario: The job records the window
- **WHEN** the stage job runs an item with a window of 8192 tokens, and the model answers a plan after one call
- **THEN** the item fails with `RoadmapStageError` and the reason names `ai.tasks.stage.context_window`

#### Scenario: A review run of fix-plan
- **WHEN** a review run of the task `fix_plan_review` has a window of 12000 tokens that ends its tools after fewer calls than the least number
- **THEN** the run raises `RoadmapStageError` that names `ai.tasks.fix_plan_review.context_window`, and not `ai.tasks.stage_review`

### Requirement: The planner window of the example ConfigMap fits a plan run
The context window of each of the tasks `stage` and `fix_plan` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first plan request and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size.

#### Scenario: The example window
- **WHEN** a test reads the windows of the tasks `stage` and `fix_plan` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first request plus the tokens of the least number of long tool answers, for each window, and the window of 65536 tokens is below that point

### Requirement: The review window of the example ConfigMap fits a review run
The context window of each of the tasks `stage_review` and `fix_plan_review` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first review request with no cited file and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size. Each task SHALL name its window, so it does not take the default window of the `ai` settings.

#### Scenario: The example window
- **WHEN** a test reads the windows of the tasks `stage_review` and `fix_plan_review` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first review request plus the tokens of the least number of long tool answers, for each window, and the default window of 32768 tokens is below that point

## REMOVED Requirements

### Requirement: The comment states why a run made no tool call
**Reason**: A plan run whose window ends its tools before the least number of calls now fails the item (#3880), so the comment of a staged item has no case "the run offered no tool".
**Migration**: The requirement "The comment states that the model chose no tool" holds the case that remains.

## MODIFIED Requirements

### Requirement: The window of the analysis task is documented with its source
The page `docs/roadmap/stage.md` SHALL state the `context_window` of the task `analysis` and the file that sets it, and the `max_input_tokens` of the model of that task and the file that sets it. The stated values SHALL equal the values in `k8s/devops/configmap.example.yaml` and `k8s/llm/gateway/config.yaml`.

#### Scenario: The page and the files agree
- **WHEN** a test reads the two files and the page
- **THEN** the page states 256,000 and `k8s/devops/configmap.example.yaml`, and 1,048,576 and `k8s/llm/gateway/config.yaml`, as the files hold them

## ADDED Requirements

### Requirement: The comment states that the model chose no tool
The comment of a staged item whose plan runs made no tool call SHALL say on how many of the requests tools were offered, and that the model called none.

#### Scenario: A run that offered tools
- **WHEN** a plan run offers tools in its one request and the model gives its plan with no tool call
- **THEN** the comment says that the run offered tools on 1 of 1 request(s) and the model called none

### Requirement: A plan run whose window ends the tools too soon fails the item
When the context window ends the tools of a plan run before the run made `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool calls, the run SHALL raise `RoadmapStageError`, whatever its reply is. The message SHALL name the window in tokens, the count of calls, the setting `ai.tasks.stage.context_window` and the parent setting `ai.tasks.analysis.context_window`. The job SHALL record that error for the item. A review run SHALL NOT raise it.

#### Scenario: The window ends the tools after one call
- **WHEN** a plan run has a window of 12000 tokens, reads a big file, and the window takes the tools after fewer calls than the least number
- **THEN** the run raises `RoadmapStageError` that names the window, `ai.tasks.stage.context_window` and `ai.tasks.analysis.context_window`, though the model gave a valid plan

#### Scenario: The window ends the tools after the least number of calls
- **WHEN** a plan run has a window that ends the tools after `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` calls or more, and the model gives its plan
- **THEN** the run returns the plan

#### Scenario: A review run
- **WHEN** a review run has a window of 12000 tokens that ends its tools after one call, and the model gives its findings
- **THEN** the run returns the findings

#### Scenario: The job records the window
- **WHEN** the stage job runs an item with a window of 8192 tokens, and the model answers a plan after one call
- **THEN** the item fails with `RoadmapStageError` and the reason names `ai.tasks.stage.context_window`

### Requirement: The planner window of the example ConfigMap fits a plan run
The context window of the task `analysis` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first plan request and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `analysis` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first request plus the tokens of the least number of long tool answers, and the window of 65536 tokens is below that point

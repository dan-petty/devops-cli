## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: The review window of the example ConfigMap fits a review run
The context window of the task `verification` in `k8s/devops/configmap.example.yaml` SHALL leave room, below the point where the run ends its tools, for the first review request with no cited file and `CONST_ROADMAP_STAGE_MIN_TOOL_CALLS` tool answers of the longest size. The task SHALL name its window, so it does not take the default window of the `ai` settings.

#### Scenario: The example window
- **WHEN** a test reads the window of the task `verification` in the example ConfigMap
- **THEN** the point where the run ends its tools is at least the tokens of the first review request plus the tokens of the least number of long tool answers, and the default window of 32768 tokens is below that point

# Spec Delta

## ADDED Requirements

### Requirement: The stage task falls back to the analysis task
The stage planner, the call that splits its groups and `devops roadmap eval stage` SHALL use the configuration of `ai.tasks.stage`. A field that `ai.tasks.stage` leaves unset SHALL take the value of `ai.tasks.analysis`. The variables `DEVOPS_CLI_AI_TASK_STAGE_PROVIDER`, `_MODEL`, `_REASONING_EFFORT` and `_OLLAMA_URLS` SHALL set the fields of the task.

#### Scenario: The stage task sets a model
- **WHEN** the config sets `ai.tasks.stage.model` to one model and `ai.tasks.analysis.model` to another
- **THEN** `ai.for_task("stage")` has the stage model and `ai.for_task("analysis")` keeps the analysis model

#### Scenario: The stage task is unset
- **WHEN** the config sets `ai.tasks.analysis.model` and `ai.tasks.analysis.context_window` and sets nothing for `ai.tasks.stage`
- **THEN** `ai.for_task("stage")` has the model and the context window of the analysis task

#### Scenario: A variable sets the stage model
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_MODEL` is set
- **THEN** `ai.for_task("stage").model` is that value

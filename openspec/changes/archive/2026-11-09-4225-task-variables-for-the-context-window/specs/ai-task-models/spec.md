## MODIFIED Requirements

### Requirement: The stage task falls back to the analysis task
The stage planner, the call that splits its groups and `devops roadmap eval stage` SHALL use the configuration of `ai.tasks.stage`. A field that `ai.tasks.stage` leaves unset SHALL take the value of `ai.tasks.analysis`. The variables `DEVOPS_CLI_AI_TASK_STAGE_PROVIDER`, `_MODEL`, `_REASONING_EFFORT`, `_OLLAMA_URLS`, `_CONTEXT_WINDOW` and `_MAX_TOKENS` SHALL set the fields of the task.

#### Scenario: The stage task sets a model
- **WHEN** the config sets `ai.tasks.stage.model` to one model and `ai.tasks.analysis.model` to another
- **THEN** `ai.for_task("stage")` has the stage model and `ai.for_task("analysis")` keeps the analysis model

#### Scenario: The stage task is unset
- **WHEN** the config sets `ai.tasks.analysis.model` and `ai.tasks.analysis.context_window` and sets nothing for `ai.tasks.stage`
- **THEN** `ai.for_task("stage")` has the model and the context window of the analysis task

#### Scenario: A variable sets the stage model
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_MODEL` is set
- **THEN** `ai.for_task("stage").model` is that value

#### Scenario: A variable sets the stage window alone
- **WHEN** `DEVOPS_CLI_AI_TASK_ANALYSIS_CONTEXT_WINDOW` is `65536` and `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `131072`
- **THEN** `ai.for_task("stage").context_window` is `131072` and `ai.for_task("analysis").context_window` is `65536`

## ADDED Requirements

### Requirement: A variable sets the window and the reply limit of a task
For each of the tasks `analysis`, `stage` and `verification`, the variable `DEVOPS_CLI_AI_TASK_<TASK>_CONTEXT_WINDOW` SHALL set `ai.tasks.<task>.context_window` and the variable `DEVOPS_CLI_AI_TASK_<TASK>_MAX_TOKENS` SHALL set `ai.tasks.<task>.max_tokens`. A variable that is not set SHALL leave the value of the config file. A value that is not a positive whole number SHALL fail the load of the settings with an error that names the variable.

#### Scenario: A variable sets the window of a task
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `131072`, or the same variable for `analysis` or `verification`
- **THEN** `ai.for_task(task).context_window` is `131072` for that task

#### Scenario: A variable sets the reply limit of a task
- **WHEN** `DEVOPS_CLI_AI_TASK_VERIFICATION_MAX_TOKENS` is `8192`, or the same variable for `analysis` or `stage`
- **THEN** `ai.for_task(task).max_tokens` is `8192` for that task

#### Scenario: A value that is no number
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `wide`
- **THEN** loading the settings fails with an error that names `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW`

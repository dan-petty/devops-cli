# ai-task-models Specification

## Purpose
Specifies AI model selection and configuration for specialized tasks including metadata generation and agent instruction synthesis.

## Requirements

### Requirement: Commands generating metadata or instruction files use metadata task settings
When `devops analyze path`, `branch`, or `pr` runs with `--enhanced`, and when `devops ai agents` runs, the LLM client SHALL use configuration from `ai.tasks.metadata` if configured, or fall back to global `ai` settings when unset.

#### Scenario: Metadata task model configured
- **WHEN** `ai.tasks.metadata.model` or `DEVOPS_CLI_AI_TASK_METADATA_MODEL` is set
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the configured metadata model

#### Scenario: Metadata task model unset
- **WHEN** `ai.tasks.metadata.model` is unset
- **THEN** `devops analyze` with `--enhanced` and `devops ai agents` initialize their LLM client with the global `ai.model` setting

### Requirement: The embedding task keeps its model when a source sets another of its fields
When a variable or a config file sets a field of `ai.tasks.embedding` other than `model`, the embedding task SHALL keep the embedding model `qwen3-embedding:0.6b` as its model.

#### Scenario: A variable sets the embedding timeout
- **WHEN** `DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT` is `45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`

#### Scenario: A config file sets the embedding timeout
- **WHEN** the project config file holds `ai.tasks.embedding.timeout: 45` and the settings load
- **THEN** `ai.tasks.embedding.model` is `qwen3-embedding:0.6b` and its timeout is `45.0`

### Requirement: The implement task serves the step with devops-coder
`ai.tasks.implement` SHALL default to the model `devops-coder` and the `context_window` 128000. `get_task_model("implement")` SHALL return the model of that task, so a config file or a variable that sets another model or window for the task changes the step.

#### Scenario: The defaults
- **WHEN** the settings load with no `ai.tasks.implement` key
- **THEN** `ai.for_task("implement")` has the model `devops-coder` and the `context_window` 128000

#### Scenario: A window set in the config file
- **WHEN** the project config file holds `ai.tasks.implement.context_window: 64000` and the settings load
- **THEN** `ai.for_task("implement").context_window` is 64000 and its model is still `devops-coder`

### Requirement: Intake proposal uses triage task settings
When roadmap intake requests a candidate proposal, the LLM client SHALL use configuration from `ai.tasks.triage` if configured, or fall back to global `ai` settings when unset.

#### Scenario: Triage task model configured
- **WHEN** `ai.tasks.triage.model` is set
- **THEN** intake initializes its LLM client with the configured triage model

#### Scenario: Triage task model unset
- **WHEN** `ai.tasks.triage.model` is unset
- **THEN** intake initializes its LLM client with the global `ai.model` setting

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

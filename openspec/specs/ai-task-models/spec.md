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

### Requirement: Each roadmap job reads a task of its own
Each model role of a roadmap job SHALL read a task of its own in `ai.tasks`: `intake`, `retitle`, `refine`, `refine_review`, `alternatives`, `consolidate`, `stage`, `stage_review`, `fix_plan`, `fix_plan_review`, `implement` or `implement_split`. A field that a task leaves unset SHALL take the value of `ai`, and of no other task. No roadmap job SHALL read the tasks `analysis`, `verification` or `triage`, and a config that sets them SHALL still load.

#### Scenario: A model for refine alone
- **WHEN** the config sets `ai.model` and `ai.tasks.refine.model`, and no other task
- **THEN** `ai.for_task("refine")` has the refine model, and `ai.for_task("alternatives")` and `ai.for_task("consolidate")` have `ai.model`

#### Scenario: The model of one job task
- **WHEN** the config sets the model of one job task other than `implement`
- **THEN** that task has the model, and each other job task other than `implement` has `ai.model`

#### Scenario: The stage task is unset
- **WHEN** the config sets `ai.tasks.analysis.model` and `ai.tasks.analysis.context_window` and sets nothing for `ai.tasks.stage`
- **THEN** `ai.for_task("stage")` has `ai.model` and `ai.context_window`

#### Scenario: The old tasks
- **WHEN** the config sets the models of `ai.tasks.analysis`, `ai.tasks.verification` and `ai.tasks.triage`
- **THEN** the settings load, and each job task other than `implement` has `ai.model`

#### Scenario: A variable sets a job task
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_REVIEW_MODEL`, `DEVOPS_CLI_AI_TASK_STAGE_REVIEW_CONTEXT_WINDOW` and `DEVOPS_CLI_AI_TASK_STAGE_REVIEW_MAX_TOKENS` are set
- **THEN** `ai.for_task("stage_review")` has the model, the window and the reply limit of the variables

#### Scenario: The stage task sets a model
- **WHEN** the config sets `ai.tasks.stage.model` to one model and `ai.tasks.analysis.model` to another
- **THEN** `ai.for_task("stage")` has the stage model and `ai.for_task("analysis")` keeps the analysis model

#### Scenario: A variable sets the stage model
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_MODEL` is set
- **THEN** `ai.for_task("stage").model` is that value

#### Scenario: A variable sets the stage window alone
- **WHEN** `DEVOPS_CLI_AI_TASK_ANALYSIS_CONTEXT_WINDOW` is `65536` and `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `131072`
- **THEN** `ai.for_task("stage").context_window` is `131072` and `ai.for_task("analysis").context_window` is `65536`

#### Scenario: Each job asks for its own task
- **WHEN** the consolidation judge, intake, retitle, the review of refine, `devops roadmap stage` and `fix-plan` build their clients, and the refine investigation and the alternatives check read their windows
- **THEN** each asks for its own task, and `fix-plan` asks for the client of `fix_plan` and reads the windows of `fix_plan` and `fix_plan_review`

### Requirement: A variable sets the window and the reply limit of a task
For each of the tasks `analysis` and `verification` and each job task other than `implement`, the variable `DEVOPS_CLI_AI_TASK_<TASK>_CONTEXT_WINDOW` SHALL set `ai.tasks.<task>.context_window` and the variable `DEVOPS_CLI_AI_TASK_<TASK>_MAX_TOKENS` SHALL set `ai.tasks.<task>.max_tokens`. A variable that is not set SHALL leave the value of the config file. A value that is not a positive whole number SHALL fail the load of the settings with an error that names the variable.

#### Scenario: A variable sets the window of a task
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `131072`, or the same variable for `analysis` or `verification`
- **THEN** `ai.for_task(task).context_window` is `131072` for that task

#### Scenario: A variable sets the reply limit of a task
- **WHEN** `DEVOPS_CLI_AI_TASK_VERIFICATION_MAX_TOKENS` is `8192`, or the same variable for `analysis` or `stage`
- **THEN** `ai.for_task(task).max_tokens` is `8192` for that task

#### Scenario: A value that is no number
- **WHEN** `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW` is `wide`
- **THEN** loading the settings fails with an error that names `DEVOPS_CLI_AI_TASK_STAGE_CONTEXT_WINDOW`

### Requirement: Intake proposal uses intake task settings
When roadmap intake requests a candidate proposal, the LLM client SHALL use configuration from `ai.tasks.intake` if configured, or fall back to global `ai` settings when unset. The task `ai.tasks.triage` SHALL NOT change the model of intake.

#### Scenario: Intake task model configured
- **WHEN** `ai.tasks.intake.model` is set
- **THEN** intake initializes its LLM client with the configured intake model

#### Scenario: Intake task model unset
- **WHEN** `ai.tasks.intake.model` is unset and `ai.tasks.triage.model` is set
- **THEN** intake initializes its LLM client with the global `ai.model` setting

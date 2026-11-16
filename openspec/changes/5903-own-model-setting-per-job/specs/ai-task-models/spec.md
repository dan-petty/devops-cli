# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: The stage task falls back to the analysis task`
- TO: `### Requirement: Each roadmap job reads a task of its own`

## MODIFIED Requirements

### Requirement: Each roadmap job reads a task of its own
Each model role of a roadmap job SHALL read a task of its own in `ai.tasks`: `intake` (intake, `devops roadmap eval intake` and `devops roadmap eval jev`), `retitle`, `refine` (the proposal and the investigation of refine), `refine_review` (the review of a refine proposal for an item of a bot), `alternatives`, `consolidate` (the judge of `devops roadmap consolidate`), `stage` (the stage planner, the call that splits its groups and `devops roadmap eval stage`), `stage_review` (the verification pass of the stage job and `devops roadmap eval verify`), `fix_plan` and `fix_plan_review` (the planner and the verification pass of `devops roadmap step fix-plan`), `implement`, and `implement_split` (the call that splits a task group of the implement job). A field that a task leaves unset SHALL take the value of `ai`, and of no other task. No roadmap job SHALL read the tasks `analysis`, `verification` or `triage`, and a config that sets them SHALL still load. The variables `DEVOPS_CLI_AI_TASK_<TASK>_PROVIDER`, `_MODEL`, `_REASONING_EFFORT`, `_OLLAMA_URLS`, `_CONTEXT_WINDOW` and `_MAX_TOKENS` SHALL set the fields of each job task except `implement`.

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

## REMOVED Requirements

### Requirement: Intake proposal uses triage task settings
**Reason**: Intake reads the task `intake`, a task of its own, and the task `triage` moves no job (#5903).
**Migration**: Set `ai.tasks.intake` in place of `ai.tasks.triage`.

## ADDED Requirements

### Requirement: Intake proposal uses intake task settings
When roadmap intake requests a candidate proposal, the LLM client SHALL use configuration from `ai.tasks.intake` if configured, or fall back to global `ai` settings when unset. The task `ai.tasks.triage` SHALL NOT change the model of intake.

#### Scenario: Intake task model configured
- **WHEN** `ai.tasks.intake.model` is set
- **THEN** intake initializes its LLM client with the configured intake model

#### Scenario: Intake task model unset
- **WHEN** `ai.tasks.intake.model` is unset and `ai.tasks.triage.model` is set
- **THEN** intake initializes its LLM client with the global `ai.model` setting

# Spec Delta

## REMOVED Requirements

### Requirement: Every chat model slot of the Service names one model except analysis
**Reason**: Each roadmap job names its own model in the template, and intake, retitle, refine and the alternatives check run on the local model (#5903, owner decisions of 2026-11-15 and 2026-11-16).
**Migration**: Set the model of a job in its own task, such as `ai.tasks.refine`.

## ADDED Requirements

### Requirement: Each roadmap job of the Service template names its own model
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model`, for the task `chat` and for each job task except `intake`, `retitle`, `refine` and `alternatives`, and `local/qwen3.8:27b` for these four tasks. It SHALL name `local/qwen3-embedding:0.6b` for the task `embedding`, and SHALL set no entry for the tasks `analysis`, `verification` and `triage`.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, `intake`, `retitle`, `refine` and `alternatives` are `openrouter/deepseek/deepseek-v4.1-flash-1017`, the model of `intake`, `retitle`, `refine` and `alternatives` is `local/qwen3.8:27b`, and the model of the task `embedding` is `local/qwen3-embedding:0.6b`

### Requirement: The job tasks of the Service template name their windows
Each job task of `k8s/devops/configmap.example.yaml` except `intake` and `retitle` SHALL set `context_window` 256000. Comments in the template SHALL give the reason and the end condition of each departure. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The window of each job
- **WHEN** the template is read
- **THEN** the `context_window` of each job task except `intake` and `retitle` is 256000, the template has no entry `analysis`, `verification` or `triage`, and the window of `stage` is not above the `max_input_tokens` of the group `deepseek-v4.1-flash-1017` in `k8s/llm/gateway/config.yaml`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `stage` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874 and Sonnet as a later trial

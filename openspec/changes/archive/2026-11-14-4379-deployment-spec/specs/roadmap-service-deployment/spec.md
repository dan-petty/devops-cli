## MODIFIED Requirements

### Requirement: Every chat model slot of the Service names one model except analysis
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `deepseek-v4.1-flash-1017` for `ai.model` and for each task of `ai.tasks` except `embedding`, SHALL give the task `stage` its own entry with `context_window` 256000, SHALL give the task `analysis` `context_window` 256000, and SHALL name `qwen3-embedding:0.6b` for the task `embedding`. Comments in the template SHALL give the reason and the end condition of each departure. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, with its parent task applied, are `deepseek-v4.1-flash-1017`, and the model of the task `embedding` is `qwen3-embedding:0.6b`

#### Scenario: The window of analysis is the window of the trial
- **WHEN** the template is read
- **THEN** the `context_window` of the tasks `analysis` and `stage` is 256000, and it is not above the `max_input_tokens` of the group `deepseek-v4.1-flash-1017` in `k8s/llm/gateway/config.yaml`

#### Scenario: The stage task has its own entry
- **WHEN** the `ai.tasks` section of the template is read
- **THEN** `stage` is an explicit key with the model `deepseek-v4.1-flash-1017` and `context_window` 256000

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `analysis` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874 and Sonnet as a later trial

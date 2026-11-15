# Spec Delta: roadmap-service-deployment

## MODIFIED Requirements

### Requirement: Every chat model slot of the Service names one model except analysis
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model` and for each task of `ai.tasks` except `embedding`, SHALL give the tasks `analysis` and `stage` `context_window` 256000, and SHALL name `local/qwen3-embedding:0.6b` for the task `embedding`. Comments in the template SHALL give the reason and the end condition of each departure. The template SHALL NOT name `claude-sonnet-5-5` for any chat slot.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, with its parent task applied, are `openrouter/deepseek/deepseek-v4.1-flash-1017`, and the model of the task `embedding` is `local/qwen3-embedding:0.6b`

#### Scenario: The window of analysis is the window of the trial
- **WHEN** the template is read
- **THEN** the `context_window` of the tasks `analysis` and `stage` is 256000, and it is not above the `max_input_tokens` of the group `deepseek-v4.1-flash-1017` in `k8s/llm/gateway/config.yaml`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `analysis` in the template are read
- **THEN** they name #4369, the date 2026-11-10, 67 USD a week, #3874 and Sonnet as a later trial

### Requirement: The stage task has its own entry
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL list `stage` as its own key of `ai.tasks` with the model `openrouter/deepseek/deepseek-v4.1-flash-1017` and `context_window` 256000.

#### Scenario: The stage task has its own entry
- **WHEN** the `ai.tasks` section of the template is read
- **THEN** `stage` is an explicit key with the model `openrouter/deepseek/deepseek-v4.1-flash-1017` and `context_window` 256000

### Requirement: The implement job runs on a hosted gateway group
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set the model of `ai.tasks.implement` and the one tier of each step class of `roadmap.implement.ladder` to a hosted group that `k8s/llm/gateway/config.yaml` serves. The `context_window` of the task SHALL NOT be above the `max_input_tokens` of that group, and SHALL hold the default step budget with the turn reserve.

#### Scenario: The template is read
- **WHEN** the template is validated as settings and the gateway config is read
- **THEN** the model of the task `implement` and each tier of each step class are a hosted group in the `model_list` of the gateway config, and the two step classes have a ladder

#### Scenario: Each step class has the one DeepSeek tier
- **WHEN** the template is validated as settings
- **THEN** the ladder of each step class holds the one tier `openrouter/deepseek/deepseek-v4.1-flash-1017`, as the cluster ConfigMap does, and a comment above the ladder says that a Sonnet tier is a later trial

#### Scenario: The window fits
- **WHEN** the window of the task `implement` is compared with the window of its group and with the step budget plus the turn reserve
- **THEN** the window is not above the window of the group and is not below the step budget plus the turn reserve

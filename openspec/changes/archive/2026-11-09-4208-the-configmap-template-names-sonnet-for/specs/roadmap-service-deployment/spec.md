## RENAMED Requirements

- FROM: `### Requirement: Every chat model slot of the Service names one model`
- TO: `### Requirement: Every chat model slot of the Service names one model except analysis`

## MODIFIED Requirements

### Requirement: Every chat model slot of the Service names one model except analysis
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `deepseek-v4.1-flash-1017` for `ai.model` and for each task of `ai.tasks` except `analysis` and `embedding`, SHALL name `claude-sonnet-5-5` with `context_window` 200000 for the task `analysis`, and SHALL name `qwen3-embedding:0.6b` for the task `embedding`. Comments in the template SHALL give the reason and the end condition of each departure.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `analysis`, `stage` and `embedding`, with its parent task applied, are `deepseek-v4.1-flash-1017`, the model of the tasks `analysis` and `stage` is `claude-sonnet-5-5`, and the model of the task `embedding` is `qwen3-embedding:0.6b`

#### Scenario: The window of analysis is the window of the trial
- **WHEN** the template is read
- **THEN** the `context_window` of the tasks `analysis` and `stage` is 200000, and it is not above the `max_input_tokens` of the group `claude-sonnet-5-5` in `k8s/llm/gateway/config.yaml`

#### Scenario: The comment of the trial is read
- **WHEN** the lines above the task `analysis` in the template are read
- **THEN** they name #4204, the date 2026-11-09, the cost of 0.27 USD for each stage case, and #3874 as the rule to return to

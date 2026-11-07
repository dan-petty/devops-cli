## MODIFIED Requirements

### Requirement: A model call in the cluster is sent at most two times
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.max_retries` to 1, and the ConfigMap that a deploy renders from it SHALL keep that value.

#### Scenario: A deploy renders the ConfigMap from the repository's template
- **WHEN** the active config sets `service.repos` and the App's settings, and the ConfigMap is rendered from `k8s/devops/configmap.example.yaml`
- **THEN** the rendered config validates as settings with `ai.max_retries` 1

## ADDED Requirements

### Requirement: Every chat model slot of the Service names one model
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `deepseek-v4.1-flash-1017` for `ai.model` and for each task of `ai.tasks` except `embedding`, and SHALL name `qwen3-embedding:0.6b` for the task `embedding`. A comment in the template SHALL name the owner decision of 2026-11-07 and the condition that ends it.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, with its parent task applied, are `deepseek-v4.1-flash-1017`, and the model of the task `embedding` is `qwen3-embedding:0.6b`

# Spec Delta: roadmap-service-deployment

## MODIFIED Requirements

### Requirement: Each roadmap job of the Service template names its own model
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL name `openrouter/deepseek/deepseek-v4.1-flash-1017` for `ai.model`, for the task `chat` and for each job task except `intake` and `retitle`, and `local/qwen3.8:27b` for these two tasks. It SHALL name `local/qwen3-embedding:0.6b` for the task `embedding`, and SHALL set no entry for the tasks `analysis`, `verification` and `triage`.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.model` and the model of each task except `embedding`, `intake` and `retitle` are `openrouter/deepseek/deepseek-v4.1-flash-1017`, the model of `intake` and `retitle` is `local/qwen3.8:27b`, and the model of the task `embedding` is `local/qwen3-embedding:0.6b`

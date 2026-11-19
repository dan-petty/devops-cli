## ADDED Requirements

### Requirement: The template loosens the stage limits and gives fix-checks the implement window
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `roadmap.stage.gate_returns` to 8, `roadmap.stage.backlog_interval_minutes` to 4 and `roadmap.stage.backlog_threshold` to 10. It SHALL set the task `ai.tasks.fix_checks` to the DeepSeek group with the `context_window` of the task `implement`.

#### Scenario: The template is read
- **WHEN** the template is validated as settings
- **THEN** a stage attempt gets 8 gate returns, the stage row runs every 4 minutes while its queue holds 10 or more items, and the fix-checks task has a window of 256,000 tokens

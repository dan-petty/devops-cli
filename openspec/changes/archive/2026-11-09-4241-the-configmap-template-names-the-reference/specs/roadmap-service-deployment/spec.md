## ADDED Requirements

### Requirement: The ConfigMap template names the reference models
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.reference_model` to `qwen3.8:27b` and `ai.reference_embedding_model` to `qwen/qwen3-embedding-8b`, so the spend reports of the Service value local tokens at the hosted prices of these two models. The comment above the keys SHALL give the owner decision, its date 2026-11-09, the three prices and the file `pricing_overrides.json` that holds them.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.reference_model` is `qwen3.8:27b` and `ai.reference_embedding_model` is `qwen/qwen3-embedding-8b`

#### Scenario: The comment is read
- **WHEN** the comment lines above `reference_model` in the template are read
- **THEN** they name the date 2026-11-09, the prices 0.035, 1.50 and 0.01, and the file `pricing_overrides.json`

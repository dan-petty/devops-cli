## MODIFIED Requirements

### Requirement: The ConfigMap template names the reference models
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `ai.reference_model` to `qwen3.8:27b` and `ai.reference_embedding_model` to `qwen/qwen3-embedding-8b`, so the spend reports of the Service value local tokens at the hosted prices of these two models. The template SHALL also set `ai.price_overrides` for both names (0.035 USD input and 1.50 USD output for the chat model, 0.01 USD input and 0 USD output for the embedding model, per million tokens), so a new data volume needs no hand step. The comment above the keys SHALL give the owner decision, its date 2026-11-09, the three prices, and the file `pricing_overrides.json` whose price wins over the price in the template.

#### Scenario: The rendered template is read
- **WHEN** the ConfigMap is rendered from the repository's template and validated as settings
- **THEN** `ai.reference_model` is `qwen3.8:27b`, `ai.reference_embedding_model` is `qwen/qwen3-embedding-8b`, and `ai.price_overrides` holds the prices 0.035 and 1.50 for the first and 0.01 and 0 for the second

#### Scenario: The comment is read
- **WHEN** the comment lines above `reference_model` in the template are read
- **THEN** they name the date 2026-11-09, the prices 0.035, 1.50 and 0.01, and the file `pricing_overrides.json`

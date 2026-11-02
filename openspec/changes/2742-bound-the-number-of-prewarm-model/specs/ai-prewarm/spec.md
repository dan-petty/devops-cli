## ADDED Requirements

### Requirement: Bounded model label cardinality
The `model` label of `devops_cli_ai_prewarms_total` SHALL hold at most one value for each configured model, one value for each model that the configured servers report, and the value `other`.

#### Scenario: Target model is not allowed
- **WHEN** The target model differs from the configured model and is not in the list that `client.list_models()` returns
- **THEN** The `model` label of `devops_cli_ai_prewarms_total` equals `other`.

#### Scenario: Target model is the configured model
- **WHEN** The target model equals `settings.ai.model`
- **THEN** The `model` label equals `bounded_label` of the configured model.

#### Scenario: Target model is server-reported
- **WHEN** The target model is in the list that `client.list_models()` returns
- **THEN** The `model` label equals `bounded_label` of the target model.

#### Scenario: Server list is unavailable
- **WHEN** `client.list_models()` raises an exception and the target model differs from the configured model
- **THEN** The `model` label equals `other`.

### Requirement: Bounded prewarm span model attribute
The `ai.model` attribute of the `ai.prewarm` span SHALL hold the same bounded value as the `model` label of `devops_cli_ai_prewarms_total`.

#### Scenario: Span attribute for a model outside the allowed set
- **WHEN** The target model differs from the configured model and is not in the list that `client.list_models()` returns
- **THEN** The `ai.model` attribute equals `other`.

#### Scenario: Span attribute for the configured model
- **WHEN** The target model equals `settings.ai.model`
- **THEN** The `ai.model` attribute equals `bounded_label` of the configured model.

#### Scenario: Span attribute when the server list is unavailable
- **WHEN** `client.list_models()` raises an exception and the target model differs from the configured model
- **THEN** The `ai.model` attribute equals `other`.

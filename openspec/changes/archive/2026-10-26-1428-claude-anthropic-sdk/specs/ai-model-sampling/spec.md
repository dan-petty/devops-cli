# Spec Delta: ai-model-sampling

## ADDED Requirements

### Requirement: Mandatory model configuration for Claude provider
The system SHALL require a non-empty `ai.model` when provider `claude` is configured. If `ai.model` is empty or unset, initialization SHALL raise a `ConfigurationError` naming `ai.model`.

#### Scenario: Empty model configuration fails for Claude
- **WHEN** provider `claude` is initialized with an empty or unset `ai.model`
- **THEN** initialization raises a `ConfigurationError` naming `ai.model`

### Requirement: Claude provider capability-driven thinking
The system SHALL query model capabilities from the Anthropic Models API or local configuration overrides (`supports_reasoning`). When adaptive thinking is supported and enabled, requests SHALL carry `thinking` with `type: "adaptive"` and `output_config.effort`, and SHALL omit `budget_tokens`.

#### Scenario: Model with adaptive thinking receives adaptive thinking payload
- **WHEN** a Claude model declares adaptive thinking capability and thinking is enabled
- **THEN** outbound request payloads contain `thinking` with `type: "adaptive"` and `output_config.effort`, and omit `budget_tokens`

#### Scenario: Model without thinking capability receives standard payload
- **WHEN** a Claude model does not declare adaptive thinking capability or thinking is disabled
- **THEN** outbound request payloads omit `thinking` and `output_config`

### Requirement: Claude provider capability-driven sampling parity
The system SHALL send `temperature` and `top_p` on both streamed and unstreamed Claude requests only when the model declares sampling support, omitting them when sampling is unsupported, when adaptive thinking is active, or when `use_model_sampling` is enabled.

#### Scenario: Claude model declaring sampling support transmits identical parameters
- **WHEN** a Claude model declares sampling support and adaptive thinking is disabled
- **THEN** streamed and unstreamed requests carry identical `temperature` and `top_p` values

#### Scenario: Claude model without sampling support omits sampling parameters
- **WHEN** a Claude model does not declare sampling support
- **THEN** streamed and unstreamed requests omit `temperature` and `top_p`

# Spec Delta

## ADDED Requirements

### Requirement: Each chat deployment of the gateway declares the window of its tier
Each `ollama_chat` deployment of the gateway config SHALL set `max_input_tokens` in its top-level `model_info`, equal to the `OLLAMA_CONTEXT_LENGTH` of its tier. No deployment SHALL set `model_info` inside `litellm_params`.

#### Scenario: The windows of the chat deployments
- **WHEN** the gateway config is loaded
- **THEN** each `ollama_chat` deployment has a `model_info.max_input_tokens` equal to the context length of the tier that its `api_base` names

#### Scenario: A model_info inside litellm_params
- **WHEN** a deployment of the gateway config sets `model_info` inside `litellm_params`
- **THEN** the check names that deployment

### Requirement: The gateway has no context-window fallback
The router settings of the gateway config SHALL NOT set `context_window_fallbacks`. No deployment has a window above the 262144 tokens of `ollama-48gib-fast`.

#### Scenario: The router settings
- **WHEN** the gateway config is loaded
- **THEN** `router_settings` has no `context_window_fallbacks`, and `enable_pre_call_checks` is true

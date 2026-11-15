# Spec Delta

## ADDED Requirements

### Requirement: The gateway router maps local and provider model aliases
`k8s/llm/gateway/config.yaml` SHALL configure `model_group_alias` under `router_settings`. It SHALL map models with the `local/` prefix to the local model groups, and models with provider prefixes to the hosted model groups. Every target in `model_group_alias` SHALL name an existing entry in `model_list`.

#### Scenario: Local model alias routing
- **WHEN** a client sends a request to `local/devops-chat`, `local/devops-coder`, or `local/qwen3.8:27b`
- **THEN** the gateway router maps the request to the corresponding local model group

#### Scenario: Hosted provider alias routing
- **WHEN** a client sends a request to `anthropic/claude-sonnet-5-5`, `gemini/gemini-3.8-flash`, or `openrouter/deepseek/deepseek-v4.1-flash-1017`
- **THEN** the gateway router maps the request to the corresponding hosted model group

#### Scenario: Every alias target exists
- **WHEN** the gateway configuration is validated
- **THEN** every alias target names an entry defined in `model_list`

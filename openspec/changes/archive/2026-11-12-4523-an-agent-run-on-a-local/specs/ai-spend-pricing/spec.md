## ADDED Requirements

### Requirement: The gateway group that answered decides whether a gateway call is local
`is_local` SHALL decide a gateway call that names no backend by the model that the reply names, and by the asked model when the reply names none. A gateway group of `CONST_AI_GATEWAY_VIRTUAL_MODELS` or a model with the prefix `ollama:` SHALL be local. Each other model that a reply names, a hosted group included, SHALL be hosted.

#### Scenario: A reply that names a local group
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` whose reply names `devops-coder` and no backend
- **THEN** it returns true

#### Scenario: A reply that names an Ollama model
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` whose reply names `ollama:qwen3-coder:30b` and no backend
- **THEN** it returns true

#### Scenario: A reply that names a hosted group
- **WHEN** `is_local` runs for a gateway call to `localhost:4000` whose reply names `deepseek-v4.1-flash-1017` and no backend
- **THEN** it returns false

#### Scenario: A reply that names another deployment model
- **WHEN** `is_local` runs for a gateway call to `localhost:4000` whose reply names `openai/gpt-4o` and no backend
- **THEN** it returns false

#### Scenario: An asked local group whose reply names no model
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` that asks for `devops-coder` and whose reply names no model and no backend
- **THEN** it returns true

### Requirement: A run on a local gateway group records local tokens
`record_run_spend` SHALL record a run whose reply names a local gateway group with the pricing source `local`, a cost of 0 USD and the label `local` `true` on `devops_cli_ai_tokens_total`, and the pricing registry SHALL log no warning for it. When the reply names another group than the asked one, the record SHALL be priced at the group that answered.

#### Scenario: A run on a local group whose reply names the group
- **WHEN** an agent run on `devops-coder` through the cluster gateway gets a reply that names `devops-coder`
- **THEN** the record has the deployment model `devops-coder`, the pricing source `local` and a cost of $0, the tokens carry `local` `true`, and no warning names `devops-coder`

#### Scenario: A local group falls back to a hosted group
- **WHEN** an agent run on `devops-coder` through the cluster gateway gets a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has the deployment model `deepseek-v4.1-flash-1017` and the pricing source `builtin:hosted_group_prices`

#### Scenario: A hosted group falls back to a local group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` through the cluster gateway gets a reply that names `devops-coder`
- **THEN** the record has the pricing source `local` and a cost of $0

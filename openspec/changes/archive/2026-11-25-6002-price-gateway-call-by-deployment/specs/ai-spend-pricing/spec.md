# ai-spend-pricing Specification Delta (#6002)

## ADDED Requirements

### Requirement: Agent gateway client captures the deployment model
The gateway HTTP client of an agent run MUST capture the `x-litellm-model-name` response header of each call and expose it on `GatewayCallModel.served_model` for agent spend hooks.

#### Scenario: An agent call answered by order 2
- **WHEN** an agent runs against a gateway stub whose reply sets `x-litellm-model-name` to `openrouter/deepseek/deepseek-v4.1-flash`
- **THEN** the spend ledger row records `served_model` as `openrouter/deepseek/deepseek-v4.1-flash`

### Requirement: Agent run is priced at the deployment that answered
Both `_spend_capability` and `record_run_spend` SHALL price a gateway agent call at the deployment model captured from `x-litellm-model-name`.

#### Scenario: An agent run answered by the order-2 deployment
- **WHEN** a test runs an agent or `record_run_spend` on a gateway stub answering with `x-litellm-model-name` set to `openrouter/deepseek/deepseek-v4.1-flash` and 1,000,000 input tokens
- **THEN** the ledger row records `openrouter/deepseek/deepseek-v4.1-flash` and 0.3 USD rather than 0.0784 USD

### Requirement: Chat call keeps the deployment price
`LLMClient` SHALL keep pricing a chat gateway call at the deployment model named in `x-litellm-model-name`.

#### Scenario: A chat call answered by the order-1 deployment
- **WHEN** a chat call through a gateway stub receives `x-litellm-model-name` set to `openrouter/deepseek/deepseek-v4.1-flash-1017` and 1,000,000 input tokens
- **THEN** the ledger row records that deployment model and 0.0784 USD

### Requirement: Answer counter keeps the group
The agent spend hooks MUST keep the reply body's model group for `asked` and `answered` labels on `devops_cli_ai_model_answers_total`.

#### Scenario: Answer counter ignores deployment header for group routing
- **WHEN** an agent runs on a gateway stub whose reply body names `deepseek-v4.1-flash-1017` and whose header names `openrouter/deepseek/deepseek-v4.1-flash`
- **THEN** `devops_cli_ai_model_answers_total` records `asked="deepseek-v4.1-flash-1017"`, `answered="deepseek-v4.1-flash-1017"`, and `fallback="false"`

### Requirement: A reply with no deployment header falls back to the group
When a gateway reply omits `x-litellm-model-name`, the client spend ledger MUST fall back to the reply body's model group and its group price.

#### Scenario: An agent reply with no deployment header
- **WHEN** an agent runs on a gateway stub whose reply omits `x-litellm-model-name` and sets body model `deepseek-v4.1-flash-1017` with 1,000,000 input tokens
- **THEN** the ledger row records `served_model` as `deepseek-v4.1-flash-1017` and 0.0784 USD

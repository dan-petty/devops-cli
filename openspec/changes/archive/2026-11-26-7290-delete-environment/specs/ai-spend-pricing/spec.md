## ADDED Requirements

### Requirement: Local savings by backend show each in-cluster service
Local savings by backend server: USD per hour SHALL show one series for each Kubernetes service of an in-cluster Ollama, with the legend `{{backend}}`. The query SHALL join the tokens on `model_id` to the service name in the `api_base` of `litellm_deployment_total_requests_total`, and a deployment with no `api_base` SHALL take the name of its `litellm_model_name`. No series SHALL name only the gateway.

#### Scenario: Two groups on one service and an embedding deployment
- **WHEN** promtool evaluates the panel over fixture series in which `ollama-48gib-fast` runs $1 an hour, two groups on `ollama-64gib-standard` run $0.50 and $0.25 an hour, an embedding deployment with no `api_base` runs $0.25 an hour, and the deployment counter also has series with no `api_base` and with no `model_id`
- **THEN** the panel gives `ollama-48gib-fast` $1, `ollama-64gib-standard` $0.75 and `qwen3-embedding:0.6b` $0.25 for the hour

## MODIFIED Requirements

### Requirement: Every hosted gateway group has a price
The pricing registry SHALL price every group of `CONST_AI_GATEWAY_HOSTED_MODELS` with no setting and no price file. For a group that genai-prices does not price, the registry SHALL take the built-in price of the group, under its route name and its deployment model.

#### Scenario: Each hosted group by both names
- **WHEN** a reply of each hosted group names the route name, or the deployment model such as `openrouter/deepseek/deepseek-v4.1-flash-1017`, and no backend, and no setting and no file price the model
- **THEN** no call has the pricing source `unknown`

#### Scenario: An agent run on the DeepSeek group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` gets a reply that names `deepseek-v4.1-flash-1017` and uses 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the record has the pricing source `builtin:hosted_group_prices` and a cost of 0.033477 USD, and `devops_cli_ai_spend_usd_total` adds 0.033477 with the `model` label `deepseek-v4.1-flash-1017`

### Requirement: A local gateway group counts as local
`is_local` SHALL count a gateway reply as local when it names a group of `CONST_AI_GATEWAY_LOCAL_GROUPS`, a model with the `local/` prefix, or a model with the `ollama/`, `ollama_chat/` or `ollama:` prefix. It SHALL keep a hosted group hosted.

#### Scenario: A local fallback
- **WHEN** a gateway reply names `ollama_chat/qwen3.8:27b`
- **THEN** `is_local` is true and the record holds the source `local`

#### Scenario: A local group outside the virtual models
- **WHEN** a gateway reply names `devops-review`, `devops-background`, `devops-triage`
- **THEN** `is_local` is true

#### Scenario: A local group with a local prefix
- **WHEN** a gateway reply names `local/devops-chat`, `local/devops-coder` or `local/qwen3.8:27b`
- **THEN** `is_local` is true

#### Scenario: A hosted group
- **WHEN** a gateway reply names `claude-sonnet-5-5`
- **THEN** `is_local` is false

#### Scenario: A hosted group with a provider prefix
- **WHEN** a gateway reply names `anthropic/claude-sonnet-5-5`
- **THEN** `is_local` is false

### Requirement: Every model of the Service template is priced or local
Every chat and embedding model that `k8s/devops/configmap.example.yaml` names SHALL be a gateway group of `CONST_AI_GATEWAY_HOSTED_MODELS` or of `CONST_AI_GATEWAY_LOCAL_GROUPS`, or a model with a local prefix. A hosted group SHALL have a price, and a local group SHALL be local.

#### Scenario: The models of the Service template
- **WHEN** the models of `ai.model`, of each task and of each tier of the implement ladder in the template are read
- **THEN** no hosted group has the pricing source `unknown`, and each local group is local

## REMOVED Requirements

### Requirement: The client price of a hosted group is the price in the gateway config
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: Each in-cluster gateway deployment has a priced provider
**Reason**: It compares product code with a gateway config, a tier manifest or a values file that devops-cli no longer holds (#7290).
**Migration**: The environment repository can compare its files with the defaults of the CLI.

### Requirement: The savings by backend name each in-cluster service
**Reason**: A scenario of it read the gateway config that devops-cli no longer holds (#7290).
**Migration**: See `Local savings by backend show each in-cluster service`.

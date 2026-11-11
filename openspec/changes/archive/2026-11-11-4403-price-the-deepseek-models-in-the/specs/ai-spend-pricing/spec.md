## REMOVED Requirements

### Requirement: The warning for an unpriced hosted model names the command that sets a price
**Reason**: Its scenarios used the DeepSeek group as the hosted model that nothing prices, and the group has a price now (#4403).
**Migration**: The requirement "A warning for a hosted model with no price names the command that sets a price" holds the same rule with a model that nothing prices.

## ADDED Requirements

### Requirement: A warning for a hosted model with no price names the command that sets a price
The warning that names a hosted model that neither genai-prices, a built-in price nor a price override prices SHALL give the command `devops ai cost set-price <model> <prompt_rate> <completion_rate>` with the model of the warning.

#### Scenario: A deployment model with no price
- **WHEN** two replies name `openrouter/example-provider/unpriced-model:floor` and no backend, and no price override exists
- **THEN** both rows have the source `unknown` and a cost of $0, and one warning names the command `devops ai cost set-price`

#### Scenario: A price override of the deployment model
- **WHEN** a price override of `unpriced-model:floor` is 0.05 USD input and 0.192 USD output per million tokens
- **THEN** a call of 1,000,000 prompt and 1,000,000 completion tokens costs 0.242 USD with the source `custom_override`

### Requirement: Every hosted gateway group has a price
The pricing registry SHALL price every hosted group of `k8s/llm/gateway/config.yaml` with no setting and no price file, under the route name of the group and under its deployment model. For a group that genai-prices does not price, the registry SHALL take the built-in price of the group.

#### Scenario: Each hosted group by both names
- **WHEN** a reply of each hosted group of the gateway config names the route name, or the deployment model such as `openrouter/deepseek/deepseek-v4.1-flash-1017:floor`, and no backend, and no setting and no file price the model
- **THEN** no call has the pricing source `unknown`

#### Scenario: An agent run on the DeepSeek group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` gets a reply that names `deepseek-v4.1-flash-1017` and uses 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the record has the pricing source `builtin:hosted_group_prices` and a cost of 0.033477 USD, and `devops_cli_ai_spend_usd_total` adds 0.033477 with the `model` label `deepseek-v4.1-flash-1017`

### Requirement: A price override wins over the built-in price of a group
`pricing_overrides.json` SHALL win over `ai.price_overrides`, and both SHALL win over the built-in price of a hosted group.

#### Scenario: A setting for the group
- **WHEN** `ai.price_overrides` holds 1.00 USD prompt for `deepseek-v4.1-flash-1017`
- **THEN** a call of 1,000,000 prompt tokens costs 1.00 USD with the source `settings:ai.price_overrides`

### Requirement: Every model of the Service template is priced or local
Every chat and embedding model that `k8s/devops/configmap.example.yaml` names SHALL be a group of the gateway config. A hosted group SHALL have a price, and a local group SHALL be local.

#### Scenario: The models of the Service template
- **WHEN** the models of `ai.model`, of each task and of each tier of the implement ladder in the template are read
- **THEN** each is a group of the gateway config, no hosted group has the pricing source `unknown`, and each local group is local

### Requirement: Cached prompt tokens cost the cached input rate
A price SHALL hold an optional cached input rate in USD per million tokens. The cost of a request SHALL price its prompt tokens that the provider read from its cache at that rate, and its other prompt tokens at the prompt rate. A price with no cached input rate SHALL price every prompt token at the prompt rate. The cached tokens SHALL count inside the prompt tokens. A run of an agent SHALL give the cached tokens of its replies.

#### Scenario: A price with a cached input rate
- **WHEN** a price of 1.00 USD prompt and 0.10 USD cached input prices 1,000,000 prompt tokens, 600,000 of them cached
- **THEN** the cost is 0.46 USD

#### Scenario: A price with no cached input rate
- **WHEN** a price of 1.00 USD prompt and no cached input rate prices 1,000,000 prompt tokens, 600,000 of them cached
- **THEN** the cost is 1.00 USD

### Requirement: The client price of a hosted group is the price in the gateway config
For each hosted group whose gateway config sets an input price, the client cost of a call SHALL be the cost at the input, cached input and output prices of that group in `k8s/llm/gateway/config.yaml`.

#### Scenario: A call with cached tokens
- **WHEN** each hosted group that sets its prices prices a call of 10,000 prompt tokens, 6,000 of them cached, and 1,000 completion tokens
- **THEN** the client cost of the call equals the cost at the prices of the gateway config, and the groups include `deepseek-v4.1-flash-1017`

## MODIFIED Requirements

### Requirement: A hosted group is priced at the model that the client asked for
When a call through the gateway names no backend and no deployment model, and the model that the client asked for is a hosted gateway group, devops-cli SHALL record the call as hosted, with the asked model as the deployment model, whatever host the gateway has. A deployment model that a reply names SHALL win over the asked model. A call to a local group SHALL stay local.

#### Scenario: A run on a hosted group whose replies name no model
- **WHEN** an agent run on `claude-sonnet-5-5` through a gateway that is the cluster host gets replies that name no model
- **THEN** the record is not local, has the deployment model `claude-sonnet-5-5`, the pricing source `genai_prices:anthropic` and a cost above $0

#### Scenario: A run on a hosted group that nothing prices
- **WHEN** an agent run on `claude-sonnet-5-5` through a gateway that is the cluster host gets a reply that names `example-provider/unpriced-model`, a hosted model that nothing prices
- **THEN** the record is not local, has the deployment model `example-provider/unpriced-model`, the pricing source `unknown` and a cost of $0, and one warning names the model

#### Scenario: A run on a local group
- **WHEN** an agent run on `devops-coder` through a gateway that is the cluster host gets replies that name no model
- **THEN** the record is local, has no deployment model and a cost of $0

#### Scenario: A reply that names another model
- **WHEN** an agent run on `claude-sonnet-5-5` gets a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has the deployment model `deepseek-v4.1-flash-1017` and the pricing source `builtin:hosted_group_prices`

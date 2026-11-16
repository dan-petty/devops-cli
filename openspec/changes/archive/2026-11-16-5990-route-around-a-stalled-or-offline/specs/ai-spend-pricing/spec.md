## MODIFIED Requirements

### Requirement: Every hosted gateway group has a price
The pricing registry SHALL price every hosted group of `k8s/llm/gateway/config.yaml` with no setting and no price file, under the route name of the group and under the deployment model of each of its deployments. For a group that genai-prices does not price, the registry SHALL take the built-in price of the group.

#### Scenario: Each hosted group by both names
- **WHEN** a reply of each hosted group of the gateway config names the route name, or the deployment model such as `openrouter/deepseek/deepseek-v4.1-flash-1017`, and no backend, and no setting and no file price the model
- **THEN** no call has the pricing source `unknown`

#### Scenario: An agent run on the DeepSeek group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` gets a reply that names `deepseek-v4.1-flash-1017` and uses 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the record has the pricing source `builtin:hosted_group_prices` and a cost of 0.033477 USD, and `devops_cli_ai_spend_usd_total` adds 0.033477 with the `model` label `deepseek-v4.1-flash-1017`

### Requirement: The client price of a hosted group is the price in the gateway config
For each hosted deployment whose gateway config sets an input price, the client cost of a call whose reply names its deployment model SHALL be the cost at the input, cached input, cache write and output prices of that deployment in `k8s/llm/gateway/config.yaml`. A deployment that sets no cached input price or no cache write price SHALL cost those tokens at its input price.

#### Scenario: A call with cached tokens
- **WHEN** each hosted deployment that sets its prices prices a call of 10,000 prompt tokens, 6,000 of them cache reads and 2,000 of them cache writes, and 1,000 completion tokens
- **THEN** the client cost of the call equals the cost at the prices of the gateway config, the groups include `deepseek-v4.1-flash-1017`, `claude-sonnet-5-5` and `claude-haiku-5-5`, and both deployments of `deepseek-v4.1-flash-1017` are checked

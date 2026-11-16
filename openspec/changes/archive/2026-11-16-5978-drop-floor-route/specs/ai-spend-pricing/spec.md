## MODIFIED Requirements

### Requirement: Every hosted gateway group has a price
The pricing registry SHALL price every hosted group of `k8s/llm/gateway/config.yaml` with no setting and no price file, under the route name of the group and under its deployment model. For a group that genai-prices does not price, the registry SHALL take the built-in price of the group.

#### Scenario: Each hosted group by both names
- **WHEN** a reply of each hosted group of the gateway config names the route name, or the deployment model such as `openrouter/deepseek/deepseek-v4.1-flash-1017`, and no backend, and no setting and no file price the model
- **THEN** no call has the pricing source `unknown`

#### Scenario: An agent run on the DeepSeek group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` gets a reply that names `deepseek-v4.1-flash-1017` and uses 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the record has the pricing source `builtin:hosted_group_prices` and a cost of 0.033477 USD, and `devops_cli_ai_spend_usd_total` adds 0.033477 with the `model` label `deepseek-v4.1-flash-1017`

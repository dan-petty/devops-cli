## ADDED Requirements

### Requirement: A hosted group is priced at the model that the client asked for
When a call through the gateway names no backend and no deployment model, and the model that the client asked for is a hosted gateway group, devops-cli SHALL record the call as hosted, with the asked model as the deployment model, whatever host the gateway has. A deployment model that a reply names SHALL win over the asked model. A call to a local group SHALL stay local.

#### Scenario: A run on a hosted group whose replies name no model
- **WHEN** an agent run on `claude-sonnet-5-5` through a gateway that is the cluster host gets replies that name no model
- **THEN** the record is not local, has the deployment model `claude-sonnet-5-5`, the pricing source `genai_prices:anthropic` and a cost above $0

#### Scenario: A run on a hosted group that nothing prices
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` through a gateway that is the cluster host gets replies that name no model
- **THEN** the record is not local, has the pricing source `unknown` and a cost of $0, and one warning names the model

#### Scenario: A run on a local group
- **WHEN** an agent run on `devops-coder` through a gateway that is the cluster host gets replies that name no model
- **THEN** the record is local, has no deployment model and a cost of $0

#### Scenario: A reply that names another model
- **WHEN** an agent run on `claude-sonnet-5-5` gets a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has the deployment model `deepseek-v4.1-flash-1017` and the pricing source `unknown`

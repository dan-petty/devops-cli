## ADDED Requirements

### Requirement: A hosted gateway call is priced at the deployment model that the gateway names
When a gateway reply names the deployment model that served the call in the `x-litellm-model-name` header, devops-cli SHALL price a hosted call at that model, which genai-prices reads as a LiteLLM model reference. When the reply names no deployment model, devops-cli SHALL price the call at the model that the client asked for. A call that a local backend served SHALL stay local.

#### Scenario: A blocking reply and a streamed reply that name `openai/gpt-4o`
- **WHEN** a `devops-chat` call through the gateway gets a reply from `https://api.openai.com` that names `openai/gpt-4o`, once as a blocking reply and once as a streamed reply
- **THEN** each row has the model `devops-chat`, the deployment model `openai/gpt-4o`, the pricing source `genai_prices:openai` and a cost of more than $0

#### Scenario: A reply that names no deployment model
- **WHEN** the reply of a hosted `devops-chat` call names no deployment model
- **THEN** the row has the model `devops-chat`, no deployment model, the pricing source `unknown` and a cost of $0

#### Scenario: An embedding request that names its deployment model
- **WHEN** a gateway embedding reply from `https://api.openai.com` names `openai/text-embedding-3-small` and counts 1,000,000 input tokens for the model `bge-m3:latest`
- **THEN** the row has the model `bge-m3:latest`, the deployment model `openai/text-embedding-3-small`, the pricing source `genai_prices:openai` and a cost of $0.02

#### Scenario: Deployment models of other providers
- **WHEN** hosted replies name `openai/gpt-4o`, `openai/text-embedding-3-small`, `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0`, `openrouter/anthropic/claude-3.5-sonnet` and two times `openai/gpt-9-preview`, and a local backend names `ollama_chat/qwen3.8:27b`
- **THEN** the pricing sources are `genai_prices:openai`, `genai_prices:openai`, `genai_prices:aws`, `genai_prices:openrouter`, two times `unknown`, and `local`, and one warning names `openai/gpt-9-preview` and the provider `litellm`

### Requirement: A price override of the deployment model prices a gateway call
When a gateway reply names a deployment model, a price override of that model SHALL price the hosted call, and a price override of the route name SHALL NOT.

#### Scenario: Price overrides of the deployment model and of the route name
- **WHEN** price overrides exist for `gpt-4o` and for `devops-chat`, and a hosted `devops-chat` reply names `openai/gpt-4o`
- **THEN** the call has the price of `gpt-4o`, and a reply that names no deployment model has the price of `devops-chat`

### Requirement: The metrics keep the model that the client asked for
devops-cli SHALL keep the model that the client asked for, such as a gateway route name, as the `model` label of the AI request, token and spend metrics of a call that the deployment model priced.

#### Scenario: A hosted call that names `openai/gpt-4o`
- **WHEN** a hosted `devops-chat` call that names `openai/gpt-4o` and counts 1,000,000 input tokens is recorded
- **THEN** the request, token and spend points have the `model` label `devops-chat`, and the spend point is $2.50

### Requirement: Each spend-ledger row records the deployment model that priced it
Each spend-ledger row SHALL store, in `served_model`, the deployment model that the gateway reply named, and no value when the reply named none.

#### Scenario: A ledger from before the column
- **WHEN** a ledger that has no `served_model` column opens and records a `devops-chat` request whose reply names `openai/gpt-4o`
- **THEN** it keeps its rows, the old rows have no deployment model, and the new row has `openai/gpt-4o`

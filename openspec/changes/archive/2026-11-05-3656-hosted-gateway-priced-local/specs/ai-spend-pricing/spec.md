## ADDED Requirements

### Requirement: A gateway reply that names a deployment model and no backend is hosted
A reply of the `gateway` provider that names a deployment model in the `x-litellm-model-name` header and names no backend in the `x-litellm-model-api-base` header SHALL count as a hosted call, whatever host the gateway has. A reply that names a backend SHALL stay decided by that backend. The lifetime report SHALL apply the same rule to the rows of the ledger, and a row of a hosted call SHALL NOT count in local savings.

#### Scenario: Hosted groups behind a loopback gateway
- **WHEN** replies to `claude-haiku-5-5`, `claude-sonnet-5-5` and `gemini-3.8-flash` through a gateway on `127.0.0.1` name `anthropic/claude-haiku-5-5`, `anthropic/claude-sonnet-5-5` and `gemini/gemini-3.8-flash` and no backend
- **THEN** the pricing sources are `genai_prices:anthropic`, `genai_prices:anthropic` and `genai_prices:google`, and each cost is more than $0

#### Scenario: A reply that names a local backend
- **WHEN** a reply names a deployment model and a cluster Ollama as its backend
- **THEN** the call is local

#### Scenario: The report counts a hosted group as hosted
- **WHEN** the ledger holds one call that names `anthropic/claude-haiku-5-5` and no backend, and one call that names neither, both sent to `localhost:4000` through the `gateway` provider
- **THEN** the report counts one local request

### Requirement: The warning for an unpriced hosted model names the command that sets a price
The warning that names a hosted model that neither genai-prices nor a price override prices SHALL give the command `devops ai cost set-price <model> <prompt_rate> <completion_rate>` with the model of the warning.

#### Scenario: The DeepSeek group has no price
- **WHEN** two replies name `openrouter/deepseek/deepseek-v4.1-flash-1017:floor` and no backend, and no price override exists
- **THEN** both rows have the source `unknown` and a cost of $0, and one warning names the command `devops ai cost set-price`

#### Scenario: A price override of the deployment model
- **WHEN** a price override of `deepseek-v4.1-flash-1017:floor` is 0.05 USD input and 0.192 USD output per million tokens
- **THEN** a call of 1,000,000 prompt and 1,000,000 completion tokens costs 0.242 USD with the source `custom_override`

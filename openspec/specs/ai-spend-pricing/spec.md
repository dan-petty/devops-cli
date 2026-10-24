# ai-spend-pricing Specification

## Purpose
How devops-cli prices the spend of AI calls and the savings of local calls: the reference price that prices the local tokens of every process, the pricing source that each spend-ledger row records, and the warning when a model or a reference model has no price.

## Requirements

### Requirement: A process sends local tokens and no local savings
devops-cli SHALL send the tokens of each AI call on `devops_cli_ai_tokens_total` with the label `local`, `true` when a local model ran them, and SHALL send no local savings in USD.

#### Scenario: Two processes with different reference models
- **WHEN** two processes with different `ai.reference_model` and `ai.reference_embedding_model` settings each make one local chat call and one local embedding request
- **THEN** both processes send the same metric points, and no point holds a price

### Requirement: One recording rule prices the local tokens of every process
The recording rule `devops_cli:ai_reference_price_usd_per_token` in `k8s/monitoring/prometheus-values.yaml` SHALL hold, for each operation and token type, genai-prices' price of the default reference model of the operation. Each savings query of the AI spend dashboard SHALL multiply the local tokens by this rule on operation and token type.

#### Scenario: The rule holds genai-prices' price of the default references
- **WHEN** the recording rules in `k8s/monitoring/prometheus-values.yaml` are read
- **THEN** for chat and embeddings, and for prompt and completion tokens, the rule holds the price that genai-prices' bundled snapshot gives the default reference model of the operation

#### Scenario: The savings queries
- **WHEN** the savings queries of `k8s/monitoring/dashboards/ai-spend.json` are read
- **THEN** each one multiplies `devops_cli_ai_tokens_total{local="true"}` by `devops_cli:ai_reference_price_usd_per_token` on operation and token type

### Requirement: A reference model with no price gives a warning and unpriced savings
When neither genai-prices nor a price override prices a reference model, the process SHALL log one warning that names the model and the setting or option that chose it. The savings of the tokens that this reference model prices SHALL be unpriced, not $0.

#### Scenario: Two reports with an unknown chat reference
- **WHEN** `ai.reference_model` is `gpt-4o-mni` and two reports run on a ledger with local chat tokens and local embedding tokens
- **THEN** one warning names `gpt-4o-mni` and `ai.reference_model`, the local cost equivalent, the counterfactual values and the hardware pay-off have no value, and the embedding tokens keep their price

#### Scenario: devops ai cost with an unknown reference model
- **WHEN** `devops ai cost report --reference-model gpt-4o-mni` runs
- **THEN** the table shows the savings as `unpriced`, the JSON output has `null`, `devops ai cost roi` says that the pay-off is not calculated, and the warning names `--reference-model`

#### Scenario: The ledger exposition with an unknown reference model
- **WHEN** the ledger is exported in Prometheus format with the reference model `gpt-4o-mni`
- **THEN** the exposition has no savings gauge and no counterfactual gauge

#### Scenario: devops config show checks both reference models
- **WHEN** `devops config show` runs with a chat reference and an embedding reference that genai-prices does not know
- **THEN** it exits 0 and logs one warning for each of them

### Requirement: Each spend-ledger row records where its price came from
Each spend-ledger row SHALL store its pricing source: `genai_prices:<provider>`, `local`, the source of a price override, or `unknown`. A row of a reply that the response cache answered SHALL store none. A hosted model that neither genai-prices nor a price override prices SHALL be recorded at $0 with the source `unknown`, and the process SHALL log one warning for each such model.

#### Scenario: Known, unknown, local and cached requests
- **WHEN** one request to `gpt-4o`, two requests to `gpt-9-preview`, one local request and one cached reply are recorded
- **THEN** the rows store `genai_prices:openai`, `unknown`, `unknown`, `local` and no source, and one warning names `gpt-9-preview`

#### Scenario: A ledger from before the column
- **WHEN** a ledger that has no `pricing_source` column opens
- **THEN** it keeps its rows and records the pricing source of each new row

### Requirement: A streamed request records provider-reported usage and leased server
devops-cli SHALL read token usage reported by streaming providers and SHALL record the leased server endpoint for multi-node streams.

#### Scenario: An OpenAI stream provides final usage
- **WHEN** an OpenAI-compatible stream returns a final usage chunk
- **THEN** prompt, completion, and reasoning tokens match the provider-reported usage

#### Scenario: An interrupted stream records spend in a finally block
- **WHEN** a client abandons a stream after receiving tokens
- **THEN** one ledger record captures the spent tokens

#### Scenario: A multi-node Ollama stream records the leased node
- **WHEN** an Ollama stream completes across multiple configured endpoints
- **THEN** the ledger server column contains the leased node address

### Requirement: Spend tracking records reasoning tokens and cost reports show reasoning share
The spend ledger SHALL record reasoning tokens for each AI request, and the cost report SHALL display reasoning share across backends and servers.

#### Scenario: A request with reasoning tokens is recorded
- **WHEN** an AI response contains reasoning tokens
- **THEN** the spend ledger stores reasoning tokens in its dedicated column and emits reasoning tokens to telemetry

#### Scenario: Cost report displays reasoning share
- **WHEN** `devops ai cost report --by backend` runs against the ledger
- **THEN** the rendered table displays a Reasoning Share column

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

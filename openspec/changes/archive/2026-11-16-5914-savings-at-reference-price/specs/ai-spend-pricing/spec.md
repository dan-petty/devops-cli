## REMOVED Requirements

### Requirement: The AI spend dashboard holds the reference prices
**Reason**: The constant held genai-prices' price of `gpt-4o` and `text-embedding-3-small`, 71 times the owner's reference price of a prompt token (#5914).
**Migration**: The requirement "The AI spend dashboard holds the reference prices of the Service" holds the rule, with the prices of `ai.reference_model` and `ai.reference_embedding_model` of the Service ConfigMap template.

### Requirement: The savings queries price every range and every token series
**Reason**: The queries read devops-cli's `local` label, which gave hosted DeepSeek tokens `local="true"` before #5874 (#5867, #5914).
**Migration**: The requirement "The savings queries price the gateway's local tokens" holds the rule, with the gateway's own token counters.

## ADDED Requirements

### Requirement: The AI spend dashboard holds the reference prices of the Service
The hidden constant `reference_price_usd_per_token` of `ai-spend.json` SHALL hold, for each operation and token type, the price that the pricing registry of the spend reports gives the reference model of the operation under the settings of `k8s/devops/configmap.example.yaml`: `ai.reference_model` for chat and `ai.reference_embedding_model` for embeddings. Its description SHALL name both models and `price_overrides`. No recording rule SHALL hold a reference price.

#### Scenario: The dashboard holds the prices of the Service ConfigMap template
- **WHEN** a test builds the pricing registry from the settings of the ConfigMap template and reads the dashboard and the Prometheus values
- **THEN** the constant holds the price of each reference model for prompt and completion tokens, its description names `qwen3.8:27b`, `qwen/qwen3-embedding-8b` and `price_overrides`, and no recording rule records a price

#### Scenario: The template holds the owner's reference prices
- **WHEN** the settings of the ConfigMap template are read
- **THEN** the reference models are `qwen3.8:27b` and `qwen/qwen3-embedding-8b`, and the registry prices them at 0.035 USD prompt and 1.50 USD completion, and 0.01 USD prompt and 0 USD completion, per million tokens

### Requirement: The savings queries price the gateway's local tokens
Each savings query of the AI spend dashboard SHALL multiply the local tokens by the constant `reference_price_usd_per_token` on operation and token type. The local tokens SHALL be the gateway's `litellm_input_tokens_metric_total` (prompt) and `litellm_output_tokens_metric_total` (completion) with `api_provider` `ollama_chat` (chat) or `ollama` (embeddings). A savings query SHALL NOT read `devops_cli_ai_tokens_total`.

#### Scenario: The savings queries
- **WHEN** the savings queries of the dashboard are read
- **THEN** there are 6, each selects both gateway token counters with `api_provider=~"ollama_chat|ollama"`, maps `ollama_chat` to chat and `ollama` to embeddings, multiplies by the constant on operation and token type, and reads no `devops_cli_ai_tokens_total`

#### Scenario: A range with hosted tokens that a client marked local
- **WHEN** the recorded answer of Prometheus to the query of "Local Cloud Savings in Range" for the 6 h to 2026-11-16T01:35Z is read, a range that starts before #5874 went live
- **THEN** the query is the query of the panel, and the answer is the total of the recorded series of `ollama_chat` and `ollama` at the dashboard prices, $0.149, and the openrouter tokens add nothing

#### Scenario: Savings in range over fixture series
- **WHEN** promtool evaluates Local Cloud Savings in Range over 24 h of gateway token series worth $2 an hour at the reference prices, with a gateway restart, hosted DeepSeek tokens and a client series that gives hosted tokens `local="true"`
- **THEN** the panel gives $48

### Requirement: A savings projection reads the last 7 days
The savings target of Projected 30-Day, 90-Day and 1-Year Run Rate SHALL read the savings rate of the last 7 days (`[7d]`), as its spend target does, and SHALL NOT read `$__range`. Its legend SHALL name the baseline.

#### Scenario: The projection does not follow the range
- **WHEN** promtool evaluates the savings target of Projected 30-Day Run Rate with a range of 6 h and of 7 d over fixture series worth $2 an hour
- **THEN** both give $1,440, the savings of 30 days at the rate of the last 7 days

### Requirement: The hourly savings panels draw bars that follow the step
Local savings: USD per hour and Local savings by backend server: USD per hour SHALL draw bars of `increase(...[$__interval])` with a Min interval of `1h`, the bars by backend SHALL stack, and both panels SHALL follow the chart rules of the dashboards. Neither panel SHALL draw a rolling line.

#### Scenario: The hourly bars add up to the savings of the range
- **WHEN** promtool adds the 24 hourly bars of Local savings: USD per hour over fixture series worth $2 an hour
- **THEN** the bars add up to $48

#### Scenario: The panel settings
- **WHEN** a test reads the two panels
- **THEN** each has the Min interval `1h`, the draw style `bars` and the unit `currencyUSD`, the bars by backend stack, and the chart rules find no problem

### Requirement: The savings by backend name each in-cluster service
Local savings by backend server: USD per hour SHALL show one series for each Kubernetes service of an in-cluster Ollama, with the legend `{{backend}}`. The query SHALL join the tokens on `model_id` to the service name in the `api_base` of `litellm_deployment_total_requests_total`, and a deployment with no `api_base` SHALL take the name of its `litellm_model_name`. No series SHALL name only the gateway.

#### Scenario: Two groups on one service and an embedding deployment
- **WHEN** promtool evaluates the panel over fixture series in which `ollama-48gib-fast` runs $1 an hour, two groups on `ollama-64gib-standard` run $0.50 and $0.25 an hour, an embedding deployment with no `api_base` runs $0.25 an hour, and the deployment counter also has series with no `api_base` and with no `model_id`
- **THEN** the panel gives `ollama-48gib-fast` $1, `ollama-64gib-standard` $0.75 and `qwen3-embedding:0.6b` $0.25 for the hour

#### Scenario: Each service of the gateway config
- **WHEN** a test applies the regex of the query to each in-cluster `api_base` of `k8s/llm/gateway/config.yaml`
- **THEN** each gives the Kubernetes service name of its host

### Requirement: Each in-cluster gateway deployment has a priced provider
Each deployment of `k8s/llm/gateway/config.yaml` with an in-cluster `api_base` SHALL name the provider `ollama_chat` for a chat model or `ollama` with `model_info.mode: embedding` for an embedding model.

#### Scenario: The providers of the in-cluster deployments
- **WHEN** a test reads the provider and the mode of each in-cluster deployment of the gateway config
- **THEN** the pairs are `ollama` with `embedding` and `ollama_chat` with `chat`

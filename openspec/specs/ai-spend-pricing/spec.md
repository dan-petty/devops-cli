# ai-spend-pricing Specification

## Purpose
How devops-cli prices the spend of AI calls and the savings of local calls: the reference price that prices the local tokens of every process, the pricing source that each spend-ledger row records, and the warning when a model or a reference model has no price.

## Requirements

### Requirement: A process sends local tokens and no local savings
devops-cli SHALL send the tokens of each AI call on `devops_cli_ai_tokens_total` with the label `local`, `true` when a local model ran them, and SHALL send no local savings in USD.

#### Scenario: Two processes with different reference models
- **WHEN** two processes with different `ai.reference_model` and `ai.reference_embedding_model` settings each make one local chat call and one local embedding request
- **THEN** both processes send the same metric points, and no point holds a price

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

### Requirement: Each HTTP attempt that reaches the gateway and fails is recorded in the spend ledger
devops-cli SHALL record each HTTP attempt that reaches the gateway and fails with finish reason `error`, the attempt's wall duration, 0 prompt and 0 completion tokens unless the provider reported usage, and the serving backend and deployment model when the error response names them. A connection that never opens SHALL NOT write a row.

#### Scenario: A gateway request fails with HTTP 500 before succeeding
- **WHEN** a chat dispatch request receives HTTP 500 on its first attempt and succeeds with HTTP 200 on its second attempt
- **THEN** two rows are recorded in the spend ledger: the first with finish reason `error` and 0 tokens, and the second with finish reason `stop`

#### Scenario: A gateway request times out waiting for response
- **WHEN** a chat dispatch request encounters a read timeout on its first attempt and succeeds on its second attempt
- **THEN** two rows are recorded in the spend ledger: the first with finish reason `error`, and the second with finish reason `stop`

#### Scenario: A connection failure writes no row
- **WHEN** a chat dispatch request encounters a connection error on its first attempt and succeeds on its second attempt
- **THEN** exactly one row is recorded in the spend ledger with finish reason `stop`

### Requirement: A successful reply takes the served model from the reply body when headers omit it
When a gateway reply contains a model in its reply body that differs from the requested model alias, and the gateway response headers omit `x-litellm-model-name`, devops-cli SHALL record the resolved model in `served_model`.

#### Scenario: A gateway reply with model in reply body
- **WHEN** a request for alias `devops-review` receives a reply with body model `gpt-oss:20b` and a serving backend header
- **THEN** the spend-ledger row records model `devops-review`, served_by with the backend header value, and served_model `gpt-oss:20b`

### Requirement: A chat call that fails in its stream is recorded as a failed attempt
When a chat call that returns one reply fails after its status line, because of an error frame, a cut stream or the response size limit, devops-cli SHALL record one row in the spend ledger with the request type `chat_dispatch`, finish reason `error`, 0 prompt and 0 completion tokens, and the serving backend that the response headers name.

#### Scenario: An error frame after a ping
- **WHEN** a chat call gets a stream with a `: ping` comment and then an error frame with `code` `"500"`
- **THEN** the spend ledger has one row with the request type `chat_dispatch` and finish reason `error`

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

### Requirement: A run records and counts the model that answered
`record_run_spend` SHALL store the model name of the replies of a run in `served_model` of the spend record, and SHALL add 1 for each reply to `devops_cli_ai_model_answers_total` with the labels `asked`, `answered`, `fallback` and `row`. `fallback` SHALL be `true` when the answered model is neither the asked model nor the asked model under a provider prefix, and `false` otherwise. A reply with no model name SHALL add no count.

#### Scenario: Another model answers
- **WHEN** a run of `claude-sonnet-5-5` ends with a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has `model` `claude-sonnet-5-5` and `served_model` `deepseek-v4.1-flash-1017`, and the count has `fallback` `true`

#### Scenario: The asked model answers under a provider prefix
- **WHEN** a run of `qwen3-coder:30b` ends with a reply that names `ollama_chat/qwen3-coder:30b`
- **THEN** the count has `fallback` `false`

#### Scenario: A reply names no model
- **WHEN** a run ends with a reply that has no model name
- **THEN** the run adds no answer count

### Requirement: A stored serving backend that no URL reader accepts is hosted
`is_local` SHALL decide the locality of a call from the stored served_by value, and SHALL NOT raise for a value that `urllib.parse.urlsplit` cannot read. Such a value names no local server, so the call SHALL count as hosted. A list of served_by values SHALL be local only when every value in it is local. A readable served_by value SHALL keep its classification.

#### Scenario: A stored served_by that urlsplit cannot read
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://[::1`
- **THEN** it returns false and raises no `ValueError`

#### Scenario: A list that holds one unreadable value
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://localhost:11434,http://[::1`
- **THEN** it returns false and raises no `ValueError`

#### Scenario: A stored local URL
- **WHEN** `is_local` runs for a gateway call whose served_by is `http://localhost:11434`
- **THEN** it returns true
- **AND** `devops ai cost report --by backend` shows the serving backend `localhost:11434`

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

### Requirement: The setting ai.price_overrides prices a model
The AI configuration SHALL hold the setting `ai.price_overrides`, a map of model name to a prompt price and a completion price in USD per million tokens, each a finite number of 0 or more. The default SHALL be an empty map. The pricing registry SHALL price a model from this setting when `pricing_overrides.json` in the data directory holds no price for it.

#### Scenario: Empty data directory
- **WHEN** `ai.price_overrides` holds 0.035 USD prompt and 1.50 USD completion for `qwen3.8:27b`, and the data directory holds no `pricing_overrides.json`
- **THEN** the price of `qwen3.8:27b` is 0.035 USD prompt and 1.50 USD completion per million tokens, and the registry logs no unpriced warning.

#### Scenario: A negative price
- **WHEN** `ai.price_overrides` holds a price below 0
- **THEN** the settings refuse it when they load.

### Requirement: The file on the volume wins over the setting for one model
When `pricing_overrides.json` and `ai.price_overrides` both price the same model, the registry MUST use the price of the file. For different models, the registry SHALL use both sources.

#### Scenario: Both sources price one model
- **WHEN** the file holds 9.0 USD prompt for `qwen3.8:27b` and the setting holds 0.035 USD
- **THEN** the price of `qwen3.8:27b` is 9.0 USD prompt.

#### Scenario: The sources price different models
- **WHEN** the setting prices `qwen3.8:27b` and the file prices `other-model`
- **THEN** the registry prices both models.

### Requirement: set-price never copies a price of the setting into the file
`devops ai cost set-price` SHALL save only the prices that a person set. It MUST NOT write a price of `ai.price_overrides` into `pricing_overrides.json`.

#### Scenario: A price for another model
- **WHEN** a person sets a price for `other-model` and the setting prices `qwen3.8:27b`
- **THEN** `pricing_overrides.json` holds `other-model` only.

#### Scenario: A hand price is removed
- **WHEN** a person sets a hand price for `qwen3.8:27b` and then removes it
- **THEN** the price of `qwen3.8:27b` is the price of the setting again.

### Requirement: Spend report and ROI accept time range and period grouping
The `devops ai cost report` and `devops ai cost roi` commands SHALL accept `--since` and `--until` for ISO dates or datetimes (UTC unless an offset is specified), and SHALL accept `--by day` and `--by week` to return spend, token and savings summaries grouped by period. The `--days N` flag SHALL remain as a short form equivalent to `--since` set to `N` days before the current time.

#### Scenario: Cost report grouped by week across a date range
- **WHEN** `devops ai cost report --since 2026-10-01 --until 2026-10-22 --by week --json` runs against a ledger
- **THEN** it outputs three period rows whose column sums equal the ungrouped report for the same date range

#### Scenario: Cost ROI grouped by week
- **WHEN** `devops ai cost roi --since 2026-10-01 --until 2026-10-22 --by week --json` runs against a ledger
- **THEN** each period row contains requests, local tokens, actual spend, local cost equivalent, and cloud spend avoided

#### Scenario: The MCP tool ai_cost_report accepts date range and grouping
- **WHEN** the MCP tool `ai_cost_report` is called with `since`, `until`, and `by`
- **THEN** it passes the options to the command line and returns the matching report

### Requirement: A warning for a hosted model with no price names the command that sets a price
The warning that names a hosted model that neither genai-prices, a built-in price nor a price override prices SHALL give the command `devops ai cost set-price <model> <prompt_rate> <completion_rate>` with the model of the warning.

#### Scenario: A deployment model with no price
- **WHEN** two replies name `openrouter/example-provider/unpriced-model:floor` and no backend, and no price override exists
- **THEN** both rows have the source `unknown` and a cost of $0, and one warning names the command `devops ai cost set-price`

#### Scenario: A price override of the deployment model
- **WHEN** a price override of `unpriced-model:floor` is 0.05 USD input and 0.192 USD output per million tokens
- **THEN** a call of 1,000,000 prompt and 1,000,000 completion tokens costs 0.242 USD with the source `custom_override`

### Requirement: Every hosted gateway group has a price
The pricing registry SHALL price every hosted group of `k8s/llm/gateway/config.yaml` with no setting and no price file, under the route name of the group and under the deployment model of each of its deployments. For a group that genai-prices does not price, the registry SHALL take the built-in price of the group.

#### Scenario: Each hosted group by both names
- **WHEN** a reply of each hosted group of the gateway config names the route name, or the deployment model such as `openrouter/deepseek/deepseek-v4.1-flash-1017`, and no backend, and no setting and no file price the model
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
For each hosted deployment whose gateway config sets an input price, the client cost of a call whose reply names its deployment model SHALL be the cost at the input, cached input, cache write and output prices of that deployment in `k8s/llm/gateway/config.yaml`. A deployment that sets no cached input price or no cache write price SHALL cost those tokens at its input price.

#### Scenario: A call with cached tokens
- **WHEN** each hosted deployment that sets its prices prices a call of 10,000 prompt tokens, 6,000 of them cache reads and 2,000 of them cache writes, and 1,000 completion tokens
- **THEN** the client cost of the call equals the cost at the prices of the gateway config, the groups include `deepseek-v4.1-flash-1017`, `claude-sonnet-5-5` and `claude-haiku-5-5`, and both deployments of `deepseek-v4.1-flash-1017` are checked

### Requirement: An agent of build_agent records and counts each model request
The spend hook of `build_agent` SHALL write one spend record for each model request, with the cached prompt tokens of the reply, and SHALL add 1 to `devops_cli_ai_model_answers_total` for a reply that names its model, with the labels of `record_run_spend`. A request SHALL add one count only.

#### Scenario: A stage, refine or alternatives run with two model requests
- **WHEN** the run of `investigate` sends two model requests in the row `refine`
- **THEN** the ledger has two records, and the answer count adds 2 with `row` `refine`

#### Scenario: A request with cached prompt tokens through the hook
- **WHEN** a request of an agent on the DeepSeek group reads 900,000 of its 1,000,000 prompt tokens from the cache of the provider
- **THEN** the record costs the cached input rate for the 900,000 tokens

### Requirement: The AI series name the job row that sent the request
`track_request_spend` SHALL add the label `row` to `devops_cli_ai_requests_total`, `devops_cli_ai_tokens_total` and `devops_cli_ai_spend_usd_total`. The value SHALL be the row of the `request_scope` context variable, or `other` outside a row. `devops roadmap implement --confirm` SHALL apply its plan in the scope of the row `implement`.

#### Scenario: A request in the stage row
- **WHEN** an agent of `build_agent` sends a request in the scope of the row `stage`
- **THEN** the request, token, spend and answer series of the request have `row` `stage`

#### Scenario: A runner Job
- **WHEN** a runner Job applies the plan of an item
- **THEN** its token and answer series have `row` `implement`

### Requirement: A chat call gives the cached prompt tokens of its reply
A chat call of `LLMClient`, streamed or not, SHALL give `track_request_spend` the prompt tokens that its reply names as cached in `usage.prompt_tokens_details.cached_tokens`. A failed attempt whose error body names that usage SHALL give them too. A call whose reply names no usage SHALL give 0 cached tokens.

#### Scenario: A chat call on the DeepSeek group with cached prompt tokens
- **WHEN** a chat call or a stream on the DeepSeek group gets a reply that names 1,000,000 prompt tokens, 900,000 of them cached, and 100,000 completion tokens
- **THEN** the ledger record costs 0.033477 USD

#### Scenario: A failed attempt whose error body names cached prompt tokens
- **WHEN** an attempt fails with an error body that names the same usage
- **THEN** its error record costs 0.033477 USD

### Requirement: Model request duration
The spend hook of `build_agent` SHALL record the seconds of each model request in `duration_seconds`, measured with a monotonic clock. It SHALL record one duration for each request, and SHALL write no spend record for a request that raises an error.

#### Scenario: One request
- **WHEN** a run on a fake model has a monotonic clock of 10.0 before the request and 10.25 after it
- **THEN** the newest record has `duration_seconds` 0.25

#### Scenario: Two requests in one run
- **WHEN** a run has monotonic readings 1.0, 1.2, 2.0 and 2.5
- **THEN** the two records have `duration_seconds` 0.2 and 0.5

#### Scenario: A failed request
- **WHEN** the model raises an error
- **THEN** the ledger holds no new record, and the start time does not carry to the next request

### Requirement: Mean duration report
The backend breakdown of the lifetime spend report SHALL give `mean_duration_seconds` as the mean of the recorded durations of the records of a backend.

#### Scenario: Two recorded durations
- **WHEN** two records of one backend have durations 0.1 and 0.3
- **THEN** the backend summary has `mean_duration_seconds` 0.2

### Requirement: The gateway group that answered decides whether a gateway call is local
`is_local` SHALL decide a gateway call that names no backend by the model that the reply names, and by the asked model when the reply names none. A gateway group of `CONST_AI_GATEWAY_VIRTUAL_MODELS` or a model with the prefix `ollama:` SHALL be local. Each other model that a reply names, a hosted group included, SHALL be hosted.

#### Scenario: A reply that names a local group
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` whose reply names `devops-coder` and no backend
- **THEN** it returns true

#### Scenario: A reply that names an Ollama model
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` whose reply names `ollama:qwen3-coder:30b` and no backend
- **THEN** it returns true

#### Scenario: A reply that names a hosted group
- **WHEN** `is_local` runs for a gateway call to `localhost:4000` whose reply names `deepseek-v4.1-flash-1017` and no backend
- **THEN** it returns false

#### Scenario: A reply that names another deployment model
- **WHEN** `is_local` runs for a gateway call to `localhost:4000` whose reply names `openai/gpt-4o` and no backend
- **THEN** it returns false

#### Scenario: An asked local group whose reply names no model
- **WHEN** `is_local` runs for a gateway call to `llm.example.com:4000` that asks for `devops-coder` and whose reply names no model and no backend
- **THEN** it returns true

### Requirement: A run on a local gateway group records local tokens
`record_run_spend` SHALL record a run whose reply names a local gateway group with the pricing source `local`, a cost of 0 USD and the label `local` `true` on `devops_cli_ai_tokens_total`, and the pricing registry SHALL log no warning for it. When the reply names another group than the asked one, the record SHALL be priced at the group that answered.

#### Scenario: A run on a local group whose reply names the group
- **WHEN** an agent run on `devops-coder` through the cluster gateway gets a reply that names `devops-coder`
- **THEN** the record has the deployment model `devops-coder`, the pricing source `local` and a cost of $0, the tokens carry `local` `true`, and no warning names `devops-coder`

#### Scenario: A local group falls back to a hosted group
- **WHEN** an agent run on `devops-coder` through the cluster gateway gets a reply that names `deepseek-v4.1-flash-1017`
- **THEN** the record has the deployment model `deepseek-v4.1-flash-1017` and the pricing source `builtin:hosted_group_prices`

#### Scenario: A hosted group falls back to a local group
- **WHEN** an agent run on `deepseek-v4.1-flash-1017` through the cluster gateway gets a reply that names `devops-coder`
- **THEN** the record has the pricing source `local` and a cost of $0

### Requirement: Each spend-ledger row records its cache read and cache write tokens
Each spend-ledger row SHALL store the prompt tokens that the provider read from its cache (`cache_read_tokens`) and the prompt tokens that it wrote to its cache (`cache_write_tokens`). Both SHALL count inside `prompt_tokens`. A ledger that was created before these columns existed SHALL gain both in place and keep its rows, which read 0 for both.

#### Scenario: A row with cache tokens
- **WHEN** the ledger records a call of 1,550 prompt tokens with 300 cache reads and 1,200 cache writes
- **THEN** the row and the record that the ledger gives back hold 300 cache reads and 1,200 cache writes

#### Scenario: A ledger created before the cache columns
- **WHEN** the ledger opens a database whose table `ai_spend_records` has no cache token columns and holds one row
- **THEN** the table has both columns, the old row reads 0 for both, and a new row keeps its counts

### Requirement: Cache write tokens cost the cache write rate
`track_request_spend` SHALL take the cache write tokens of a call and give them, with the cache read tokens, to the genai-prices price, which costs each at the cache rate of the model. A price override or a built-in group price, which names no cache write rate, SHALL cost a cache write token at the prompt rate.

#### Scenario: Sonnet cache prices
- **WHEN** a gateway call of `claude-sonnet-5-5` uses 2,000,000 prompt tokens, of which 1,000,000 are cache reads and 1,000,000 are cache writes
- **THEN** the call costs 2.60 USD with the pricing source `genai_prices:anthropic`, not 4.00 USD at the input price

#### Scenario: Haiku cache prices
- **WHEN** a gateway call of `claude-haiku-5-5` uses 50,000 prompt tokens, of which 20,000 are cache reads and 20,000 are cache writes
- **THEN** the call costs 0.0037 USD

### Requirement: Each caller gives the cache write tokens of its replies
The spend hook of `build_agent` SHALL give the cache write tokens of each reply (`RequestUsage.cache_write_tokens`). `record_run_spend` SHALL give the sum of the cache write tokens of the replies of a run. A chat call of `LLMClient`, blocking or streamed, SHALL give the cache write tokens that its reply names in `usage.prompt_tokens_details.cache_write_tokens`, and 0 when the reply names none.

#### Scenario: A request of an agent on a Claude group
- **WHEN** a request of an agent on `claude-sonnet-5-5` reports 2,000,000 prompt tokens with 1,000,000 cache reads and 1,000,000 cache writes
- **THEN** the record stores both counts and costs 2.60 USD

#### Scenario: A run of two replies
- **WHEN** a run on `claude-sonnet-5-5` gets two replies, each with 1,000,000 prompt tokens, 500,000 cache reads and 500,000 cache writes
- **THEN** the record stores 1,000,000 cache reads and 1,000,000 cache writes and costs 2.60 USD

#### Scenario: A blocking or streamed chat call on a Claude group
- **WHEN** a chat call or a stream on `claude-sonnet-5-5` gets a reply whose usage names 2,000,000 prompt tokens, 1,000,000 `cached_tokens` and 1,000,000 `cache_write_tokens`
- **THEN** the ledger record stores both counts and costs 2.60 USD

### Requirement: A build_agent request names its served backend
The spend hook of `build_agent` SHALL pass `served_by` to `track_request_spend`, so the backend breakdown counts the request and the price follows the backend that served it.

#### Scenario: A request with a served backend
- **WHEN** an agent of `build_agent` runs on a model whose `served_by` is a backend URL
- **THEN** the lifetime report holds one backend entry with that URL and one request

#### Scenario: A hosted backend behind the gateway
- **WHEN** the `served_by` is a hosted API URL
- **THEN** the request is priced at the model that the reply names, not at zero

### Requirement: A local gateway group counts as local
`is_local` SHALL count a gateway reply as local when it names a local group of `k8s/llm/gateway/config.yaml`, a model with the `local/` prefix, or a model with the `ollama/`, `ollama_chat/` or `ollama:` prefix. It SHALL keep a hosted group hosted.

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

### Requirement: Spend and local savings follow the backend route
All traffic routed to a `*.local` `api_base` SHALL count as local savings, unless `served_by` names the AI gateway proxy endpoint itself. All requests not routed to a `*.local` `api_base` SHALL count as spend. When `served_by` names the gateway proxy endpoint, model routing rules SHALL decide whether the call is local savings or spend.

#### Scenario: Traffic routed to a cluster local backend
- **WHEN** a request has `served_by` set to `http://ollama-48gib-fast.llm.svc.cluster.local:11434`
- **THEN** `is_local` is true and the tokens carry `local` `true`

#### Scenario: Traffic routed to a cloud backend
- **WHEN** a request has `served_by` set to an RFC 1918 private address or an internal domain
- **THEN** `is_local` is false, `devops_cli_ai_spend_usd_total` records the spend, and the tokens carry `local` `false`

#### Scenario: Request names the gateway proxy endpoint as served_by
- **WHEN** a request names the gateway proxy endpoint `http://llm-gateway.llm.svc.cluster.local:4000/v1` in `served_by` for a hosted model
- **THEN** `is_local` is false, `devops_cli_ai_spend_usd_total` records the spend, and the tokens carry `local` `false`

### Requirement: A Jev decision call is recorded in the spend ledger
Each Jev decision call SHALL add one row to the spend ledger with the model `typesafe/jev-1.14`, the prompt and output tokens of the answer, and the cost of those tokens at the Jev price of 0.042 USD per million input tokens with no output charge. The call SHALL record the row after it gets the answer, in `decide_with_jev` and in the decision of `roadmap intake`.

#### Scenario: One call through the Jev fake
- **WHEN** one decision call runs against `JevFake`, which answers 64 input tokens
- **THEN** the ledger holds one row for `typesafe/jev-1.14` with 64 prompt tokens and a cost that is the price of those tokens

#### Scenario: A cost report after one call
- **WHEN** one Jev call is recorded and `devops ai cost report --by model` runs
- **THEN** the report lists `typesafe/jev-1.14` with a non-zero token count

### Requirement: The Jev price is a built-in default
The pricing registry SHALL hold the Jev price in its built-in prices, so a call is priced with no setting and no file. `ai.price_overrides` and the file of `set-price` SHALL win over it, and the Service ConfigMap SHALL set the same rates.

#### Scenario: A workstation with no setting prices a Jev call
- **WHEN** the registry builds with no `ai.price_overrides` and no price file
- **THEN** it prices one million input tokens of `typesafe/jev-1.14` at 0.042 USD

### Requirement: A failed spend record leaves the Jev answer
A Jev call MUST return its answer when the spend record cannot be written or the answer names no usage.

#### Scenario: The ledger write fails
- **WHEN** the ledger raises during the record of a Jev call
- **THEN** the call returns its typed answer and the caller sees no exception

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

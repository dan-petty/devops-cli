# gateway-caller-telemetry Specification

## Purpose
How the callers of the LLM gateway are named and counted: the headers that devops-cli sends to name itself and its service, the gateway's `end_user` label, Open WebUI's one path through the gateway, and the panels of the AI spend dashboard that read the gateway's own series.

## Requirements

### Requirement: A call to the gateway names devops-cli and its service
Each devops-cli chat call, embedding call and pydantic-ai model call to the gateway SHALL send `User-Agent: devops-cli/<release>` and `x-litellm-end-user-id` with the process's OTel service name. A call to another provider SHALL send no `x-litellm-end-user-id`.

#### Scenario: A chat call to the gateway
- **WHEN** an `LLMClient` with provider `gateway` sends a chat call, with `OTEL_SERVICE_NAME` unset or set to `roadmap-service`
- **THEN** the request's User-Agent is `devops-cli/<release>` and its `x-litellm-end-user-id` is `devops-cli` or `roadmap-service`

#### Scenario: An embedding call to the gateway
- **WHEN** an embeddings engine with provider `gateway` embeds one text
- **THEN** the request's User-Agent is `devops-cli/<release>` and its `x-litellm-end-user-id` is the process's service name

#### Scenario: A pydantic-ai agent call to the gateway
- **WHEN** a pydantic-ai agent runs on a model that `resolve_pydantic_ai_model` sends to the gateway
- **THEN** the request's User-Agent is `devops-cli/<release>`, not pydantic-ai's, and its `x-litellm-end-user-id` is the process's service name

#### Scenario: A chat call to another provider
- **WHEN** an `LLMClient` with provider `openai` sends a chat call
- **THEN** the request has no `x-litellm-end-user-id`

### Requirement: The broker names the installed release
The HTTP broker's default User-Agent SHALL be `devops-cli/<release>` of the installed release.

#### Scenario: The broker's request headers
- **WHEN** the broker builds the headers of a request that sets no User-Agent
- **THEN** the User-Agent is `devops-cli/<release>`

### Requirement: The gateway writes the caller on its series
The gateway config SHALL set `litellm_settings.enable_end_user_cost_tracking_prometheus_only` to `true`.

#### Scenario: The gateway config
- **WHEN** `k8s/llm/gateway/config.yaml` is read
- **THEN** `litellm_settings.enable_end_user_cost_tracking_prometheus_only` is `true`

### Requirement: Open WebUI calls models only through the gateway
The Open WebUI values SHALL name no Ollama URL, and SHALL connect its OpenAI API and its RAG embeddings to the gateway.

#### Scenario: The Open WebUI values
- **WHEN** `k8s/llm/values-open-webui.yaml` is read
- **THEN** it has no `ollamaUrls`, its OpenAI base URL is the gateway's, and its RAG embedding engine is `openai` at the gateway's URL

### Requirement: The request and token counts take gateway traffic from the gateway
AI Requests in Range SHALL count the gateway's chat and embedding requests with a 2xx status, and devops-cli's requests with `provider!="gateway"` and `cached="false"`. Tokens Processed in Range SHALL count the gateway's total tokens, and devops-cli's tokens with `provider!="gateway"`, `server!="cache"` and `type!="reasoning"`. Neither SHALL select devops-cli's `provider="gateway"` series.

#### Scenario: The two stat panels
- **WHEN** the queries of AI Requests in Range and Tokens Processed in Range are read
- **THEN** each selects one gateway series and one devops-cli series with the matchers above, and neither names `provider="gateway"`

### Requirement: The dashboard shows the gateway's attempts, callers and coverage
The AI spend dashboard SHALL hold Gateway Attempts by Status (the gateway's chat and embedding requests by `status_code`), Gateway Requests and Tokens by Caller (its replied requests and its tokens by `end_user`), and devops-cli Coverage of Gateway Spend (devops-cli's `provider="gateway"` spend over the gateway's spend counter `litellm_spend_metric_total`, as a stat in percent that shows red under 0.95 and over 1.05).

#### Scenario: The gateway row
- **WHEN** the three panels are read
- **THEN** the attempts group by `status_code` and match no status, the caller panel's two queries group by `end_user`, and the coverage stat divides `devops_cli_ai_spend_usd_total{provider="gateway"}` by `litellm_spend_metric_total`, in `percentunit`, with the threshold steps red, 0.95 text and 1.05 red

#### Scenario: The coverage of the fixture series
- **WHEN** promtool evaluates the coverage stat over 24 h of fixture series in which devops-cli counts $0.75 of each $1 that the gateway counts
- **THEN** the stat gives 0.75

### Requirement: The dashboard reads only gateway series that the gateway serves
Each gateway series that `ai-spend.json` reads SHALL be in the LiteLLM capture with each label that a query matches or groups by, and SHALL be read through `rate(` or `increase(`. A label that the query sets with `label_replace` SHALL need no gateway series that carries it, and a gateway label name in a string of the query SHALL NOT count as a read of a series.

#### Scenario: A raw read of a gateway counter
- **WHEN** a query reads `litellm_total_tokens_metric_total` outside `rate(` and `increase(`
- **THEN** the check names that read

#### Scenario: A label that the query sets
- **WHEN** a query groups by `backend`, which a `label_replace` of the query sets from `litellm_model_name`, and another query groups by `backend` with no `label_replace`
- **THEN** the check names only the second query

### Requirement: An empty service name still names devops-cli
`gateway_caller_headers` SHALL return a non-empty value for `x-litellm-end-user-id` on every gateway request, and the value SHALL be `devops-cli` when the process's OTel service name is empty.

#### Scenario: An empty OTel service name
- **WHEN** `OTEL_SERVICE_NAME` is set to an empty string
- **THEN** a chat call, an embedding call and a pydantic-ai agent call each send `x-litellm-end-user-id: devops-cli`

### Requirement: The gateway drops the caller address and user agent
The `http` endpoint of the LLM gateway ServiceMonitor SHALL hold one `metricRelabelings` entry with `action: labeldrop` for each of `client_ip` and `user_agent`, and SHALL keep its port, path and interval.

#### Scenario: The endpoint holds one labeldrop rule for each label
- **WHEN** a check reads `k8s/llm/gateway/servicemonitor.yaml` and collects the `regex` of every `metricRelabelings` entry with `action: labeldrop` on the `http` endpoint
- **THEN** the collected values are exactly `client_ip` and `user_agent`, and the endpoint still names port `http`, path `/metrics/` and interval `15s`

### Requirement: No query reads the dropped labels
Every query of `k8s/devops/dashboards/ai-spend.json` and `k8s/monitoring/dashboards/llm-stack.json` and every alert expression of `k8s/monitoring/prometheus-values.yaml` that reads a `litellm_` series MUST NOT group by or filter on `client_ip` or `user_agent`.

#### Scenario: The dashboards and the alerts ignore the labels
- **WHEN** a check reads the target expressions of both dashboards and the `serverFiles.alerting_rules.yml` expressions of the Prometheus values
- **THEN** no expression names `client_ip` or `user_agent`

### Requirement: The manifest check runs in the k8s row
The labeldrop check SHALL run in the `k8s` row of `devops ci`, which the Static Analysis check runs.

#### Scenario: The k8s row reports the check
- **WHEN** the `k8s` row runs the `check_*` functions under `tests/gate/k8s_checks/`
- **THEN** the three gateway label checks report a pass

### Requirement: The spend panels take gateway spend from the gateway
Cloud Spend in Range, the spend target of each projection, Spend: USD per hour and Spend by provider and model: USD per hour SHALL read the gateway's spend counter `litellm_spend_metric_total` for a call through the gateway, and `devops_cli_ai_spend_usd_total{provider!="gateway"}` for a call that did not go through the gateway. No spend panel SHALL select devops-cli's `provider="gateway"` spend. Each stat SHALL fall back to 0 for each counter.

#### Scenario: Spend in range adds the gateway and the direct calls
- **WHEN** promtool evaluates Cloud Spend in Range over 24 h of fixture series: the gateway counter at $1 an hour, devops-cli's gateway spend at $0.75 an hour and its direct spend at $0.25 an hour
- **THEN** the panel gives $30, and devops-cli's gateway spend adds nothing

#### Scenario: The panel queries
- **WHEN** a test reads the spend targets of the six spend panels
- **THEN** each reads both counters, each devops-cli spend selector is `devops_cli_ai_spend_usd_total{provider!="gateway"}`, and each stat falls back to 0

### Requirement: A spend projection reads the last 7 days
The spend target of Projected 30-Day, 90-Day and 1-Year Run Rate SHALL read the spend rate of the last 7 days (`[7d]`), and SHALL NOT read `$__range`.

#### Scenario: The projection does not follow the range
- **WHEN** promtool evaluates the spend target of Projected 30-Day Run Rate with a range of 6 h and of 7 d
- **THEN** both give $900, the spend of 30 days at the rate of the last 7 days

### Requirement: The hourly spend panels draw bars that follow the step
Spend: USD per hour and Spend by provider and model: USD per hour SHALL draw bars of `increase(...[$__interval])` with a Min interval of `1h`, and SHALL follow the chart rules of the dashboards, so they SHALL NOT use `or vector(0)`.

#### Scenario: The hourly bars add up to the spend of the range
- **WHEN** promtool adds the 24 hourly bars of Spend: USD per hour and of Spend by provider and model: USD per hour over the fixture series
- **THEN** the bars of Spend: USD per hour add up to $30, and the bars by provider and model give $24 for the hosted model, $6 for the direct model and no bar for the local model that spent $0

#### Scenario: The panel settings
- **WHEN** a test reads the two panels
- **THEN** each has the Min interval `1h`, the draw style `bars` and the unit `currencyUSD`, and the chart rules find no problem

### Requirement: The spend by provider panel names the provider first
The panel Spend by provider and model: USD per hour SHALL name the hosted provider first in its title and in each legend: `{{api_provider}}: {{model}}` for a call through the gateway and `{{provider}}: {{model}}` for a direct call.

#### Scenario: The legends
- **WHEN** a test reads the targets of the panel
- **THEN** the legends are `{{api_provider}}: {{model}}` and `{{provider}}: {{model}}`

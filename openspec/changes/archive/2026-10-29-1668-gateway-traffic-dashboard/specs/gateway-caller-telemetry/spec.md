## Purpose

How the callers of the LLM gateway are named and counted: the headers that devops-cli sends to name itself and its service, the gateway's `end_user` label, Open WebUI's one path through the gateway, and the panels of the AI spend dashboard that read the gateway's own series.

## ADDED Requirements

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
The AI spend dashboard SHALL hold Gateway Attempts by Status (the gateway's chat and embedding requests by `status_code`), Gateway Requests and Tokens by Caller (its replied requests and its tokens by `end_user`), and devops-cli Coverage of Gateway Requests (devops-cli's replied gateway calls over the gateway's replied requests, as a stat in percent).

#### Scenario: The gateway row
- **WHEN** the three panels are read
- **THEN** the attempts group by `status_code` and match no status, the caller panel's two queries group by `end_user`, and the coverage stat divides devops-cli's `provider="gateway"` requests by the gateway's 2xx requests, in `percentunit`

### Requirement: The dashboard reads only gateway series that the gateway serves
Each gateway series that `ai-spend.json` reads SHALL be in the LiteLLM capture with each label that a query matches or groups by, and SHALL be read through `rate(` or `increase(`.

#### Scenario: A raw read of a gateway counter
- **WHEN** a query reads `litellm_total_tokens_metric_total` outside `rate(` and `increase(`
- **THEN** the check names that read

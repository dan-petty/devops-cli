## MODIFIED Requirements

### Requirement: Hosted groups call a provider with an optional key
The gateway config SHALL serve the groups `gemini-3.8-flash`, `claude-sonnet-5-5`, `claude-haiku-5-5` and `deepseek-v4.1-flash-1017`. Each SHALL name a `gemini`, `anthropic` or `openrouter` backend with no `api_base`, set its window, and read its key from a variable of the gateway Deployment that is an optional key of the Secret `llm-gateway-secrets`. A hosted group with more than one deployment SHALL give each deployment its own `order`.

#### Scenario: A hosted group without its key
- **WHEN** the gateway starts with no `GEMINI_API_KEY`
- **THEN** it serves every group, and a call to `gemini-3.8-flash` fails with an error that names the missing key

#### Scenario: The OpenRouter group without its key
- **WHEN** the gateway starts with no `OPENROUTER_API_KEY`
- **THEN** it serves every group, and a call to `deepseek-v4.1-flash-1017` fails with an error that names the missing key

#### Scenario: Two deployments with one order
- **WHEN** a test edit gives both deployments of `deepseek-v4.1-flash-1017` the order 1
- **THEN** the hosted-group check fails

### Requirement: The dated DeepSeek group falls back to the undated model with the same provider filter
The group `deepseek-v4.1-flash-1017` SHALL have two deployments: order 1 calls `openrouter/deepseek/deepseek-v4.1-flash-1017` with `allowed_fails: 0` and `cooldown_time: 120`, and order 2 calls `openrouter/deepseek/deepseek-v4.1-flash`. A call that neither deployment can answer SHALL fall back to the group `deepseek-v4.1-flash`. Each deployment of both groups SHALL keep the fp8 and `data_collection: deny` filters, the same window and `supports_response_schema`.

#### Scenario: A stall of the dated model moves the next call
- **WHEN** order 1 sends a 408 inside the stream of a call
- **THEN** that call fails, and the next call goes to order 2 in less than 1 s

#### Scenario: A timeout of the dated group falls back
- **WHEN** a call of `deepseek-v4.1-flash-1017` comes while both of its deployments are cooled
- **THEN** the gateway sends the call to `deepseek-v4.1-flash`

#### Scenario: The fallback keeps the privacy filter
- **WHEN** the gateway config is read
- **THEN** each deployment of both DeepSeek groups asks OpenRouter for fp8 weights and `data_collection: deny`

#### Scenario: Both groups take a structured reply
- **WHEN** the gateway config is read
- **THEN** each deployment of both DeepSeek groups sets `supports_response_schema: true`

## ADDED Requirements

### Requirement: Health checks cover only the hosted DeepSeek groups
The gateway SHALL run background health checks every 60 s with health-check routing for the groups `deepseek-v4.1-flash-1017` and `deepseek-v4.1-flash` only. Each of their deployments SHALL end its check in 30 s. A deployment that sets its own `cooldown_time` SHALL set it to at least the interval plus the check time. No Ollama group SHALL get a health check.

#### Scenario: A stalled check moves the new calls
- **WHEN** order 1 of `deepseek-v4.1-flash-1017` gives no reply to its health check in 30 s
- **THEN** the next calls of the group go to order 2, and no call fails on order 1 first

#### Scenario: A recovered deployment gets its calls back
- **WHEN** a later health check of order 1 passes, and order 1 is not cooled
- **THEN** the next calls of the group go to order 1 again

#### Scenario: The scope of the checks
- **WHEN** the gateway config is read
- **THEN** the checked groups are the two DeepSeek groups, and no checked deployment calls an Ollama tier

### Requirement: The router counts failures below the LiteLLM default
`router_settings.allowed_fails` SHALL be above 0 and below 3, the LiteLLM default. At the default, LiteLLM 1.103.11 counts no failures and never cools a group with one deployment.

#### Scenario: An offline Ollama tier
- **WHEN** a group with one deployment and a fallback fails on each retry of a call
- **THEN** the gateway cools the deployment, and the next calls go to the fallback with no wait

#### Scenario: The value of the gateway config
- **WHEN** the gateway config is read
- **THEN** `router_settings.allowed_fails` is above 0 and below 3

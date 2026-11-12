## ADDED Requirements

### Requirement: The LLM stack time series follow the rate interval and draw one line per entity
Each time series target of `llm-stack.json` SHALL hold no range window but `[$__rate_interval]`. A breakdown panel SHALL draw no mean or rolling line. Only "Calls in Flight per Deployment", "Requests per Deployment" and "GPU Power" SHALL add `Total (Sum)`, as `sum(<refId A query>)`. "GPU Memory Used" SHALL use the unit `mbytes`, because DCGM gives the value in MiB.

#### Scenario: No time series target holds a fixed window
- **WHEN** the range windows of the time series targets of `llm-stack.json` are read
- **THEN** each window is `[$__rate_interval]`

#### Scenario: Only calls, requests and power add a total
- **WHEN** the breakdown panels of `llm-stack.json` are read
- **THEN** "Calls in Flight per Deployment", "Requests per Deployment" and "GPU Power" hold refId A and a `Total (Sum)` target equal to `sum(<refId A query>)`
- **AND** "GPU Utilisation", "GPU Memory Used" and "GPU Memory Utilization (%)" hold only refId A
- **AND** each field override names a line the panel draws
- **AND** "GPU Memory Used" has the unit `mbytes`

### Requirement: The LLM stack request panels count only model routes
"Requests per Virtual Model" and "Responses by Status Code" SHALL select `litellm_proxy_total_requests_metric_total` with `route=~"/v1/(chat/completions|embeddings)"`, as `ai-spend.json` does, so a gateway route that is not a model call is not counted.

#### Scenario: The request panels filter the route
- **WHEN** the queries of "Requests per Virtual Model" and "Responses by Status Code" are read
- **THEN** each selects `route=~"/v1/(chat/completions|embeddings)"`

### Requirement: The LLM stack counts cooldowns and fallbacks in the time range
"Cooldowns per Deployment in Range" and "Fallbacks per Model Pair in Range" SHALL be stat panels of instant `increase(...[$__range])` queries with no constant fallback. With no series they SHALL show "none recorded".

#### Scenario: The cooldown and fallback panels are stats of the range
- **WHEN** the cooldown and fallback panels of `llm-stack.json` are read
- **THEN** each is a stat panel with `noValue` "none recorded"
- **AND** each target is an instant `increase` over `[$__range]`

### Requirement: The Qdrant row draws each value once on its own scale
"Qdrant Request Rate and Errors" SHALL have one target by method, endpoint and status. "Qdrant Collections" SHALL be a stat of `sum(collections_total)`, and "Qdrant Vectors per Collection" SHALL draw `collection_vectors` by collection.

#### Scenario: The Qdrant row splits collections from vectors
- **WHEN** the Qdrant panels of `llm-stack.json` are read
- **THEN** "Qdrant Request Rate and Errors" holds one target
- **AND** "Qdrant Collections" is a stat of `sum(collections_total)`
- **AND** "Qdrant Vectors per Collection" draws `sum by (collection) (collection_vectors)`

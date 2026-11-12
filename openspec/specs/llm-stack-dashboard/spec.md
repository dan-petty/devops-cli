# llm-stack-dashboard Specification

## Purpose
The panels of the LLM stack dashboard `k8s/monitoring/dashboards/llm-stack.json`, "LLM Gateway & GPUs", and the gateway series that each panel shows.

## Requirements

### Requirement: The LLM stack dashboard shows the latency per output token beside the time to the first token
The LLM stack dashboard SHALL have one panel that shows the p50 and the p95 of the gateway histogram `litellm_deployment_latency_per_output_token` for each deployment, grouped by `api_base` and `litellm_model_name`, in seconds. The panel SHALL be in the row of the panel "Time to First Token p95 per Model", directly to its right. The panel SHALL have a description that says what the gateway measures.

#### Scenario: The panel is beside the time-to-first-token panel
- **WHEN** the panels of `llm-stack.json` are read
- **THEN** one panel, "Latency per Output Token (p50 / p95) per Deployment", selects `litellm_deployment_latency_per_output_token_bucket`
- **AND** its two queries take the quantiles 0.5 and 0.95, each grouped by `le`, `api_base` and `litellm_model_name`
- **AND** its unit is `s`, it has a description, and its position is on the row of "Time to First Token p95 per Model", at the column where that panel ends

### Requirement: The GPU row shows clock-event reasons, power against the enforced limit and PCIe throughput
The GPU row of `llm-stack.json` SHALL have the panels "GPU Power against Enforced Limit (%)", "GPU Clock Event Reasons (Samples in 5 Minutes)" and "GPU PCIe Throughput". Each panel SHALL select only DCGM families in `tests/fixtures/metrics/dcgm-exporter.yaml` and SHALL have a description.

#### Scenario: The GPU row holds the three panels over captured fields
- **WHEN** the panels between the row "GPUs" and the next row of `llm-stack.json` are read
- **THEN** "GPU Clock Event Reasons (Samples in 5 Minutes)" selects `DCGM_EXP_CLOCK_EVENTS_COUNT` with unit `short`
- **AND** "GPU Power against Enforced Limit (%)" selects `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_FI_DEV_POWER_USAGE` with unit `percent`
- **AND** "GPU PCIe Throughput" selects `DCGM_FI_PROF_PCIE_RX_BYTES` and `DCGM_FI_PROF_PCIE_TX_BYTES` with unit `Bps`
- **AND** every family that these panels select is in the DCGM capture, and each panel has a description

#### Scenario: The power panel draws the enforced limit on its axis
- **WHEN** the thresholds of "GPU Power against Enforced Limit (%)" are read
- **THEN** it draws a threshold line at 100
- **AND** its `axisSoftMax` reaches that line

#### Scenario: The clock-event panel leaves out an idle GPU
- **WHEN** the query of "GPU Clock Event Reasons (Samples in 5 Minutes)" is read
- **THEN** it groups by `hostname`, `gpu`, `modelName` and `clock_event`
- **AND** it matches `clock_event!="gpu_idle"`

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

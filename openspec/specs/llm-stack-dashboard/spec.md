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

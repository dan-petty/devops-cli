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

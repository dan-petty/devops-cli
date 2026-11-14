## ADDED Requirements

### Requirement: The LLM stack dashboard shows overview gauge panels at the top
The LLM stack dashboard `k8s/monitoring/dashboards/llm-stack.json` SHALL have an "Overview" row at position `y: 0`, followed by three gauge panels at `y: 1`: "Cluster GPU Compute Utilization", "Cluster GPU Memory Utilization", and "Gateway Request Success Rate". Each panel SHALL have width 8 and height 6, and select only metric families from the DCGM or LiteLLM captures.

#### Scenario: The overview row and gauge panels exist at the top
- **WHEN** the panels of `llm-stack.json` are read
- **THEN** a row titled "Overview" is at position `y: 0`
- **AND** three gauge panels are at position `y: 1` with width 8 and height 6
- **AND** "Cluster GPU Compute Utilization" selects `DCGM_FI_DEV_GPU_UTIL`
- **AND** "Cluster GPU Memory Utilization" selects `DCGM_FI_DEV_FB_USED` and `DCGM_FI_DEV_FB_FREE`
- **AND** "Gateway Request Success Rate" selects `litellm_deployment_success_responses_total` and `litellm_deployment_total_requests_total`

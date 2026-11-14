# Proposal: #5727

## Why
The LLM stack dashboard `k8s/monitoring/dashboards/llm-stack.json` starts directly with granular time-series panels in the "LLM Pool Load" row. Operators cannot quickly evaluate high-level health and utilization of the cluster GPU hardware and LLM gateway at a glance. Closes #5727.

## What Changes
- Add an "Overview" row panel at `y: 0` in `k8s/monitoring/dashboards/llm-stack.json`.
- Add three top gauge panels side-by-side (`w: 8, h: 6, y: 1`):
  1. "Cluster GPU Compute Utilization": `avg(DCGM_FI_DEV_GPU_UTIL)`
  2. "Cluster GPU Memory Utilization": `100 * sum(DCGM_FI_DEV_FB_USED) / sum(DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)`
  3. "Gateway Request Success Rate": `100 * sum(rate(litellm_deployment_success_responses_total{api_base!=""}[$__rate_interval])) / sum(rate(litellm_deployment_total_requests_total{api_base!=""}[$__rate_interval]))`
- Shift all existing panels down by `y += 7` to maintain relative layout and structure.
- Add unit tests in `tests/commands/k8s/test_stack_dashboards.py` to assert the presence, configuration, queries, and layout of the new overview gauges.

## Capabilities
- `llm-stack-dashboard`: Add overview gauge panels at the top of the LLM stack dashboard.

## Impact
Improves operator visibility into cluster-wide GPU utilization and gateway success rate without degrading dashboard performance or violating metric capture constraints.

## Feasibility
All PromQL metrics are backed by existing captures (`tests/fixtures/metrics/dcgm-exporter.yaml` and `tests/fixtures/metrics/litellm.yaml`). Queries pass `_gateway_violations` and `dashboard_violations` in `tests/commands/k8s/test_stack_dashboards.py`.

## Existing Tool Considered
Grafana native gauge panels and standard DCGM/LiteLLM Prometheus metric families. Using native Grafana panels requires zero custom libraries or code.

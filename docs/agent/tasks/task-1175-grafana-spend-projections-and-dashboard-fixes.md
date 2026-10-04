# Task: Grafana Dashboard Projections, Rolling Averages, and Panel Queries (#1175)

**Issue**: [#1175](https://github.com/dan-petty/devops-cli/issues/1175)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p2-medium
**Scope**: type/bug, scope/telemetry, scope/k8s

## Description
Remediates multi-series rolling average sprawl, time-range spend and savings projections, empty panel queries, node exporter metric allowlists, and dashboard panel grid layouts across the Grafana monitoring stack:

1. **Dashboard Rolling Averages Aggregation**: In `ai-spend.json`, converted multi-series rolling average queries that generated one rolling average line per item into single aggregate totals (`Total Rolling Avg`) across all items.
2. **AI Spend & Local Savings Projections**: In `ai-spend.json`, updated 30-day, 90-day, and 1-year run rate projection stat panels to extrapolate from the observed dashboard time range (`rate(...[$__range])`) multiplied out for each projection window, replacing the fixed 1-hour rate window.
3. **LLM Gateway Time to First Token**: In `llm-stack.json`, resolved empty panel by querying `histogram_quantile(0.95, sum by (le, model) (rate(litellm_llm_api_time_to_first_token_metric_bucket[5m])))`, removing the broken `model_id` join on ephemeral LiteLLM hash identifiers.
4. **Node Exporter Full Dropdown Selectors**: In `k8s-monitoring-values.yaml`, enabled `useIntegrationAllowList: true` and added `node_uname_info`, `node_load.*`, `node_disk_io_now`, and `node_netstat_Tcp_CurrEstab` to `includeMetrics`, restoring host metric series required for dashboard 1860 dropdown selectors and system metrics.
5. **NVIDIA DCGM Exporter Grid Layout**: Provisioned local dashboard `nvidia-dcgm.json` with a 2x2 grid layout for bottom panels (GPU SM Clocks, GPU Utilization, Tensor Core Utilization, GPU Framebuffer Memory Used) at width 12 and height 8, replacing upstream dashboard 12239's single-column 50% row layout.
6. **Project & Engineering Velocity Metrics**: In `project-metrics.json`, changed snapshot counters (`devops_cli_project_*`) to query series values directly rather than applying `increase()`, and exempted static snapshot counters from rate-or-increase rules in tests.
7. **Ingress & Cloudflare Tunnel Traffic**: In `ingress-tunnel.json`, ensured "Traffic by Ingress Host / Router" gracefully handles router traffic with service traffic fallback.

## Acceptance Criteria
- [x] In `ai-spend.json`, rolling averages on panels 8, 10, 11, and 15 compute an aggregate sum across all items labeled `Total Rolling Avg (...)`.
- [x] In `ai-spend.json`, 30-day, 90-day, and 1-year projection panels calculate rates over `[$__range]` extrapolated to 30d, 90d, and 365d.
- [x] In `llm-stack.json`, Time to First Token p95 queries `litellm_llm_api_time_to_first_token_metric_bucket` grouped by `(le, model)`.
- [x] In `k8s-monitoring-values.yaml`, `useIntegrationAllowList` is set to `true` and `includeMetrics` includes `node_uname_info`, `node_load.*`, `node_disk_io_now`, and `node_netstat_Tcp_CurrEstab`.
- [x] `nvidia-dcgm.json` positions bottom panels in a 2x2 grid `((0, 16), (12, 16), (0, 24), (12, 24))` and is registered in `kustomization.yaml`.
- [x] `project-metrics.json` displays current snapshot values without `increase()` on cumulative release counters.
- [x] `ingress-tunnel.json` Traffic by Ingress Host / Router provides clean router/service metric evaluation.
- [x] Unit tests in `tests/test_grafana_dashboards.py`, `tests/test_telemetry_instruments.py`, and `tests/test_k8s_monitoring_integration.py` pass.
- [x] All 10 CI quality gates pass via `uv run devops ci`.
- [x] `changelog.d/1175.md` records the changes.

## Deliverables
- [x] `k8s/monitoring/dashboards/ai-spend.json`: Consolidated rolling averages and dynamic time-range projection rates.
- [x] `k8s/monitoring/dashboards/llm-stack.json`: LiteLLM TTFT p95 per model metric query without volatile hash joins.
- [x] `k8s/monitoring/k8s-monitoring-values.yaml`: Enabled integration allowlist and added required node-exporter series.
- [x] `k8s/monitoring/dashboards/nvidia-dcgm.json`: 2x2 panel layout for DCGM metrics.
- [x] `k8s/monitoring/grafana-values.yaml` & `k8s/monitoring/dashboards/kustomization.yaml`: Configured local dashboard delivery for DCGM.
- [x] `k8s/monitoring/dashboards/project-metrics.json`: Corrected snapshot counter query semantics.
- [x] `k8s/monitoring/dashboards/ingress-tunnel.json`: Resilient traffic router/service query.
- [x] `tests/test_grafana_dashboards.py` & `tests/test_telemetry_instruments.py` & `tests/test_k8s_monitoring_integration.py`: Test assertions updated.
- [x] `changelog.d/1175.md`: Release notes fragment.

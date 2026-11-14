# Design

## Decisions
- Panel layout:
  - Add an "Overview" row header (id: 35, y: 0, w: 24, h: 1).
  - Add three gauge panels (ids: 36, 37, 38) at `y: 1` with `h: 6, w: 8`:
    - `x: 0`: "Cluster GPU Compute Utilization"
    - `x: 8`: "Cluster GPU Memory Utilization"
    - `x: 16`: "Gateway Request Success Rate"
- Query selection:
  - GPU compute utilization uses `avg(DCGM_FI_DEV_GPU_UTIL)` with thresholds at 70 (warning) and 90 (critical).
  - GPU memory utilization uses `100 * sum(DCGM_FI_DEV_FB_USED) / sum(DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)` with thresholds at 80 (warning) and 95 (critical).
  - Gateway request success rate uses `100 * sum(rate(litellm_deployment_success_responses_total{api_base!=""}[$__rate_interval])) / sum(rate(litellm_deployment_total_requests_total{api_base!=""}[$__rate_interval]))` with thresholds at 95 (warning) and 99 (ok/green).
- Coordinate transformation:
  - All existing panels in `llm-stack.json` shift down by `y += 7`. Existing row groupings and relative positions remain identical.

## Rejected alternatives
- Separate overview dashboard: Rejected because operators need immediate visual status upon loading the primary `llm-stack` dashboard.
- Stat panels instead of gauges: Rejected because gauge visualizations clearly indicate operational headroom against defined threshold limits.

# Task: SRE Dashboards Heatmap and Ratio-Based Graphs (#938)

**Issue**: [#938](https://github.com/dan-petty/devops-cli/issues/938)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/telemetry, scope/k8s

## Description
The SRE Grafana dashboards (`ingress-tunnel.json` and `sre-service.json`) lacked latency distribution heatmaps and ratio-based timeseries graphs for saturation and error triage:

- **Lack of Latency Distribution Heatmaps**: Service and ingress latency visualizations relied exclusively on linear percentile lines (p50/p95/p99) or average durations, masking multi-modal distributions, traffic spikes, and outlier clusters that are immediately visible in histogram heatmaps.
- **Missing Ratio-Based Metrics**:
  - Ingress and Cloudflare Tunnel dashboards lacked percentage ratio tracking of error rates relative to total requests (`cloudflared_tunnel_request_errors` / `cloudflared_tunnel_total_requests`) and HTTP response code ratios (`2xx/3xx %`, `4xx %`, `5xx %`).
  - Service dashboards lacked saturation ratios comparing pod container CPU and memory usage against configured Kubernetes limits (`kube_pod_container_resource_limits`), as well as CFS CPU throttling ratios (`container_cpu_cfs_throttled_periods_total` / `container_cpu_cfs_periods_total`) and network packet drop ratios (`container_network_receive_packets_dropped_total` + transmit / total packets).

## Key Changes
1. **Ingress & Cloudflare Tunnel Dashboard (`ingress-tunnel.json`)**:
   - Added Panel 23: **Cloudflare Tunnel Request Error Ratio (%)** (timeseries, y=13, h=7, w=24) tracking tunnel error percentages with smooth line interpolation and zero-divisor clamping guards.
   - Added Panel 24: **Ingress HTTP Status Code Ratios (Success vs. Error %)** (timeseries, y=33, h=8, w=12) displaying `2xx/3xx Success Ratio %`, `4xx Client Error Ratio %`, and `5xx Server Error Ratio %`.
   - Added Panel 25: **Ingress Request Latency Distribution (Heatmap)** (heatmap, y=33, h=8, w=12) visualizing `traefik_service_request_duration_seconds_bucket` distributions across ingress services.
   - Realiged downstream panels and rows to prevent grid overlaps.
2. **Service Performance Dashboard (`sre-service.json`)**:
   - Added Panel 13: **Container Resource Saturation Ratios (% of Limit)** (timeseries, y=14, h=8, w=12) calculating pod CPU and memory saturation percentages against Kubernetes limits.
   - Added Panel 14: **Service Request Duration Distribution (Heatmap)** (heatmap, y=14, h=8, w=12) rendering duration bucket distributions for the selected service.
   - Added Panel 15: **CPU Throttling & Network Packet Drop Ratios (%)** (timeseries, y=30, h=8, w=24) tracking CFS throttling percentage and network packet drop rates per pod.
   - Realigned network timeseries and live Loki log stream panels to preserve seamless layout and grid geometry.
3. **Automated Testing & Static Linting**:
   - Added `test_sre_dashboards_contain_heatmap_and_ratio_panels` to `tests/test_grafana_dashboards.py` with structural tuple equality assertions.
   - Verified static linting with `devops grafana dashboards lint k8s/monitoring/dashboards` (0 errors, 0 warnings across all 12 dashboards / 251 panels).
   - Deployed updated `grafana-stack-dashboards` ConfigMap to Kubernetes.

## Acceptance Criteria
- [x] `ingress-tunnel.json` contains Cloudflare Tunnel error ratio %, HTTP status code ratios %, and request latency distribution heatmap.
- [x] `sre-service.json` contains container resource saturation ratios % of limit, request duration distribution heatmap, and CPU throttling & packet drop ratios %.
- [x] All 12 dashboards in `k8s/monitoring/dashboards` pass `devops grafana dashboards lint` with 0 errors and 0 warnings.
- [x] Unit tests in `tests/test_grafana_dashboards.py` pass with consolidated tuple equality assertions.
- [x] `uv run devops ci` quality gates pass with 100% success.

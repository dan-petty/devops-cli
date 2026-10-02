# Task: Grafana Service & Cluster Workload Graphs Sum & Average Lines (#968)

**Issue**: [#968](https://github.com/dan-petty/devops-cli/issues/968)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/telemetry, scope/k8s

## Description
Grafana time-series graphs across service, ingress, Kubernetes pod/node, and LLM cluster dashboards show multi-series breakdowns (per pod, per service, per container, or per deployment) but lacked clear aggregate baseline lines.

To provide immediate visibility into both aggregate workload volume and per-instance average baselines alongside individual components, dedicated PromQL queries were added to the primary multi-series timeseries panels with clear, standardized labels:
- **`Total (Sum)`**: `sum(...)` across all component series in the scope.
- **`Average (Mean)`**: `avg(...)` across all component series in the scope.

## Key Changes
1. **SRE Service Performance Dashboard (`sre-service.json`)**:
   - Added `Total (Sum)` and `Average (Mean)` targets to **CPU Usage by Pod** (`sum(rate(container_cpu_usage_seconds_total...))` and `avg(rate(...))`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **Memory Working Set by Pod** (`sum(container_memory_working_set_bytes...)` and `avg(...)`).
2. **Ingress & Cloudflare Tunnel Dashboard (`ingress-tunnel.json`)**:
   - Added `Total (Sum)` and `Average (Mean)` targets to **Service Request Rate** (`sum(rate(traefik_service_requests_total...))` and `avg(...)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **Ingress & Tunnel Pod CPU Usage** (`sum(rate(container_cpu_usage_seconds_total...))` and `avg(...)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **Ingress & Tunnel Memory Working Set** (`sum(container_memory_working_set_bytes...)` and `avg(...)`).
3. **Kubernetes Views - Nodes Dashboard (`k8s-views-nodes.json`)**:
   - Added `Total (Sum)` and `Average (Mean)` targets to **CPU usage by Pod** (`sum(rate(container_cpu_usage_seconds_total...))` and `avg(...)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **Memory usage by Pod** (`sum(container_memory_working_set_bytes...)` and `avg(...)`).
4. **Kubernetes Views - Pods Dashboard (`k8s-views-pods.json`)**:
   - Added `Total (Sum)` and `Average (Mean)` targets to **CPU Usage by container** (`sum(rate(container_cpu_usage_seconds_total...))` and `avg(...)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **Memory Usage by container** (`sum(container_memory_working_set_bytes...)` and `avg(...)`).
5. **LLM Gateway & GPUs Dashboard (`llm-stack.json`)**:
   - Added `Total (Sum)` and `Average (Mean)` targets to **Requests per Deployment** (`sum(rate(litellm_deployment_total_requests_total...))` and `avg(...)`).
   - Added `Average (Mean)` target to **GPU Utilisation** (`avg(DCGM_FI_DEV_GPU_UTIL)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **GPU Memory Used** (`sum(DCGM_FI_DEV_FB_USED)` and `avg(...)`).
   - Added `Total (Sum)` and `Average (Mean)` targets to **GPU Power** (`sum(DCGM_FI_DEV_POWER_USAGE)` and `avg(...)`).
6. **Automated Verification & Tests**:
   - Added `test_dashboards_contain_properly_labeled_sum_and_average_lines` to `tests/test_grafana_dashboards.py` with structural tuple equality assertions.
   - Verified static linting with `devops grafana dashboards lint k8s/monitoring/dashboards` (0 errors, 0 warnings across all 12 dashboards / 251 panels).
   - Verified all ConfigMap sizes stay safely within the 262,144-byte kubectl last-applied annotation limit via `tests/test_k8s_monitoring_dashboards.py`.
   - Verified exporter coverage and schema conformance via `tests/test_stack_dashboards.py`.

## Acceptance Criteria
- [x] `sre-service.json` contains `Total (Sum)` and `Average (Mean)` targets for CPU and memory usage graphs.
- [x] `ingress-tunnel.json` contains `Total (Sum)` and `Average (Mean)` targets for request rate, CPU usage, and memory usage graphs.
- [x] `k8s-views-nodes.json` and `k8s-views-pods.json` contain `Total (Sum)` and `Average (Mean)` targets for CPU and memory breakdown graphs.
- [x] `llm-stack.json` contains `Total (Sum)` and `Average (Mean)` targets for requests, GPU memory, and GPU power graphs, and `Average (Mean)` for GPU utilisation.
- [x] All 12 dashboards in `k8s/monitoring/dashboards` pass `devops grafana dashboards lint` with 0 errors and 0 warnings.
- [x] Unit tests in `tests/test_grafana_dashboards.py` pass with consolidated tuple equality assertions.
- [x] `uv run devops ci` quality gates pass with 100% success.

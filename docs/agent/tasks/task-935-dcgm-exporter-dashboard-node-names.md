# Task: NVIDIA DCGM Exporter Dashboard Node Names Relabeling (#935)

**Issue**: [#935](https://github.com/dan-petty/devops-cli/issues/935)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p2-medium
**Scope**: scope/k8s, scope/telemetry

## Description
The NVIDIA DCGM Exporter Grafana dashboard (`nvidia-dcgm-exporter-dashboard`, ID 12239) and DCGM Prometheus metrics displayed raw pod IP addresses (e.g., `10.42.0.236:9400`) instead of human-readable Kubernetes node names (`condor`, `gemini`, `hawk`, `hog`) in the `$instance` dropdown filter and panel legends.

Unlike `node-exporter`, which relabels `__meta_kubernetes_pod_node_name` to `instance`, `dcgm-exporter` had no relabelings defined in its Helm chart values (`k8s/monitoring/dcgm-exporter-values.yaml`). Upstream Grafana dashboard 12239 populates its `$instance` variable via `label_values(DCGM_FI_DEV_GPU_TEMP, instance)` and executes queries with `{instance=~"${instance}", gpu=~"${gpu}"}`. Because `instance` defaulted to the scrape target address (`pod_ip:9400`), operators had to correlate IP addresses manually to determine which physical machine hosted each GPU.

## Key Changes
1. **DCGM Scrape Relabeling**:
   - Updated `k8s/monitoring/dcgm-exporter-values.yaml` to add Prometheus `serviceMonitor.relabelings`:
     - Relabel `__meta_kubernetes_pod_node_name` to `node` (action: `replace`, targetLabel: `node`).
     - Relabel `__meta_kubernetes_pod_node_name` to `instance` (action: `replace`, targetLabel: `instance`).
   - Ensures all `DCGM_FI_*` metrics published by DCGM Exporter carry both `node` and `instance` labels set to the Kubernetes node name.
2. **Metrics Fixtures & Test Assertions**:
   - Updated `tests/fixtures/metrics/dcgm-exporter.yaml` to include `node` in `target_labels`.
   - Updated `tests/test_k8s_monitoring_integration.py` (`test_dcgm_exporter_values_timeout_and_capabilities`) to verify `serviceMonitor.relabelings` mapping `__meta_kubernetes_pod_node_name` to both `node` and `instance`.
3. **OpenTelemetry Collector Loki Exporter Realignment**:
   - Replaced removed `loki` exporter with standard `otlp_http/loki` pointing to `http://loki.logging.svc.cluster.local:3100/otlp` in `k8s/otel/values.yaml` and updated `tests/test_k8s_monitoring_integration.py`.
   - Restored clean Helm upgrade and log forwarding for OpenTelemetry Collector to Loki.
4. **Cluster Stack Deployment & Live Validation**:
   - Applied changes using `devops k8s deploy-stack --stack all`.
   - Verified DCGM Exporter metrics and Grafana dashboard panels resolve Kubernetes node names.

## Acceptance Criteria
- [x] `k8s/monitoring/dcgm-exporter-values.yaml` defines `serviceMonitor.relabelings` replacing `node` and `instance` with `__meta_kubernetes_pod_node_name`.
- [x] Metrics fixtures in `tests/fixtures/metrics/dcgm-exporter.yaml` declare `node` target label.
- [x] Unit test `test_dcgm_exporter_values_timeout_and_capabilities` passes and validates relabelings.
- [x] OpenTelemetry Collector deploys cleanly with `otlp_http/loki` exporter.
- [x] `devops k8s deploy-stack --stack all` deploys cleanly.
- [x] DCGM Prometheus metrics (`DCGM_FI_*`) display node names for `instance`.
- [x] `uv run devops ci` passes all quality gates.

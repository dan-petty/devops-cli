# Task: Grafana K8s Monitoring Missing Metrics, SRE Service Dashboard and OTel Loki Exporter (#922)

**Issue**: [#922](https://github.com/dan-petty/devops-cli/issues/922)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/k8s

## Description
Grafana dashboards exhibited missing metrics following the migration to `k8s-monitoring` Helm charts, workloads lacked a dedicated per-service SRE dashboard with integrated logs, and OpenTelemetry collector log ingestion was not reaching Loki:

- **Missing Node & Container Metrics**: In `k8s/monitoring/k8s-monitoring-values.yaml`, `useIntegrationAllowList: true` discarded standard Linux host metrics (disk I/O, detailed network series) required by `node-exporter-full` and `k8s-views-nodes.json`. Additionally, cAdvisor omitted container CPU usage seconds, memory working set bytes, and network packet/drop counters.
- **OpenTelemetry Logs Pipeline**: In `k8s/otel/values.yaml`, the OTel collector had a debug exporter on the logs pipeline but no Loki exporter. Logs were not forwarded to the in-cluster Loki endpoint, and network policies did not permit OTel collector egress to Loki port 3100.
- **Dedicated SRE Service Dashboard**: Workloads lacked a unified service dashboard displaying Golden Signals (CPU, Memory, Bandwidth, Packet Drops), pod readiness/restarts, and a correlated Loki logs stream.
- **Sidecar Auto-Provisioning**: Stack dashboards were not included in the sidecar `ConfigMapGenerator` in `k8s/monitoring/dashboards/kustomization.yaml`.

## Key Changes
1. **OTel Loki Exporter & Network Policies**: Added a `loki` exporter (`http://loki.logging.svc.cluster.local:3100/loki/api/v1/push`) to `k8s/otel/values.yaml` and attached it to `service.pipelines.logs.exporters`. Updated `k8s/logging/networkpolicy.yaml` to permit Loki ingress from namespace `otel` on port 3100, and unified `k8s/otel/networkpolicy.yaml` into a single perimeter NetworkPolicy `otel-default-perimeter` permitting egress to Loki (3100), Alloy (9090), and CoreDNS (53).
2. **Restore Node & Container Metrics**: Set `hostMetrics.linuxHosts.metricsTuning.useIntegrationAllowList: false` in `k8s/monitoring/k8s-monitoring-values.yaml` and added `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, `container_network_receive_packets_total`, `container_network_transmit_packets_total`, `container_network_receive_packets_dropped_total`, and `container_network_transmit_packets_dropped_total`.
3. **SRE Service Dashboard**: Created `k8s/monitoring/dashboards/sre-service.json` (UID: `devops-sre-service`) with `$namespace`, `$service`, and `$pod` templating variables, resource saturation charts, and an embedded Loki logs viewer. Extended `src/devops_cli/grafana/schema.py` to preserve dashboard variables and descriptions.
4. **Sidecar Auto-Provisioning**: Added `grafana-stack-dashboards` to `k8s/monitoring/dashboards/kustomization.yaml` provisioning `sre-service.json`, `llm-stack.json`, `otel-collector.json`, and `prometheus-server.json` via the Grafana sidecar ConfigMap (total size ~65KB, well below the 256KB annotation cap).

## Acceptance Criteria
- [x] OTel collector logs pipeline exports OTLP logs to Loki in `logging` namespace.
- [x] Network policies permit OTel collector egress to Loki (3100) and Alloy (9090), and Loki ingress from `otel`.
- [x] `k8s-monitoring` provides complete Node Exporter and cAdvisor metrics without allowlist truncation.
- [x] SRE Service Dashboard (`sre-service.json`) is created, lints cleanly, and is auto-provisioned via `grafana-stack-dashboards`.
- [x] All integration tests in `tests/test_k8s_monitoring_integration.py`, `tests/test_k8s_monitoring_dashboards.py`, `tests/test_k8s_network_policies.py`, and `tests/test_k8s_logging_stack.py` pass.
- [x] `uv run devops ci` passes with 100% success across all quality gates.

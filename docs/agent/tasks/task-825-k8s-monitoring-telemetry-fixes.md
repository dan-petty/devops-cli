# Task 825: Kubernetes Monitoring Telemetry Integration & Dashboard Metric Fixes

**Issue**: [#825](https://github.com/dan-petty/devops-cli/issues/825)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Resolves missing metrics and empty/zero-value panels across Kubernetes Grafana dashboards (Views: Global, Namespaces, Pods, Nodes; NVIDIA DCGM Exporter; OpenTelemetry & Jaeger Traces; LLM & Vector Stack).

### Root Causes & Telemetry Vectors Addressed:
1. **NVIDIA DCGM Exporter Dashboard & GPU Metrics**:
   - The deployed `dcgm-exporter` ServiceMonitor had `interval: 15s` and default `scrapeTimeout: 25s`, causing Grafana Alloy to reject the scrape configuration (`scrape timeout greater than scrape interval`).
   - Pods on datacenter GPU nodes lacked `SYS_ADMIN` capability in the deployed release, leading to `Host engine is running as non-root` failures.
2. **Kubernetes Views (Global, Namespaces, Pods, Nodes)**:
   - `kube-state-metrics` omitted `metricLabelsAllowlist`, which defaulted to only allowing `nodes=[...]`. Consequently, `kube_namespace_labels`, `kube_deployment_labels`, `kube_statefulset_labels`, `kube_daemonset_labels`, `kube_hpa_labels`, and `kube_networkpolicy_labels` were never generated.
   - KSM active collectors lacked `endpoints`, preventing `kube_endpoint_info` from being emitted.
   - Alloy's cAdvisor and KSM allowlists dropped key operational metrics (`container_cpu_cfs_throttled_seconds_total`, `container_oom_events_total`, `container_network_receive_errors_total`, `container_network_transmit_errors_total`, `kube_hpa_labels`, `kube_pod_container_status_ready`, `kube_pod_container_status_last_terminated_exitcode`, `kube_pod_container_status_terminated`, `kube_pod_container_status_waiting`, `kube_deployment_status_replicas_unavailable`).
3. **OpenTelemetry & Jaeger Traces**:
   - The OpenTelemetry Collector Helm values lacked an enabled `serviceMonitor`, so its internal metrics port `8888` was never scraped, causing `otelcol_receiver_accepted_spans` and `otelcol_receiver_accepted_metric_points` to return empty/0.
4. **Qdrant Vector Database**:
   - Qdrant Helm values lacked an enabled `metrics.serviceMonitor`, causing vector collection and HTTP operation metrics (`collections_total`, `app_http_requests_total`) to return empty/0 in the LLM & Vector Stack dashboard.
5. **CoreDNS NetworkPolicy Egress**:
   - In `monitoring/networkpolicy.yaml`, egress to `kube-system` allowed port 53 (DNS) but omitted port 9153 (CoreDNS metrics endpoint), causing Prometheus scrape attempts to fail with connection refused.

---

### Key Deliverables Completed:
- [x] **Kubernetes Monitoring Stack Configuration** (`k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/monitoring/networkpolicy.yaml`):
  - Configured `telemetryServices.kube-state-metrics.metricLabelsAllowlist` for namespaces, deployments, statefulsets, daemonsets, horizontalpodautoscalers, networkpolicies, persistentvolumeclaims, pods, services, ingresses, and nodes.
  - Enabled `collectorsExtra: [endpoints]` in KSM to emit `kube_endpoint_info`.
  - Added missing container CFS throttling, OOM events, and network error metrics to `clusterMetrics.cadvisor.metricsTuning.includeMetrics`.
  - Added missing container status and workload label metrics to `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`.
  - Added port 9153 (TCP) to `monitoring-default-perimeter` NetworkPolicy egress to allow CoreDNS metrics scraping.
- [x] **OpenTelemetry Collector Configuration** (`k8s/otel/values.yaml`):
  - Enabled `serviceMonitor` for OpenTelemetry Collector to scrape internal metrics on port `metrics` (8888).
- [x] **Qdrant Vector Database Configuration** (`k8s/llm/values-qdrant.yaml`):
  - Enabled `metrics.serviceMonitor` with a 15-second scrape interval.
- [x] **Automated Regression Test Suite** (`tests/test_k8s_monitoring_integration.py`):
  - Authored unit test assertions verifying cAdvisor and KSM metrics tuning, KSM metric labels allowlist, collectors extra, monitoring NetworkPolicy egress rules, OTel collector ServiceMonitor, and Qdrant ServiceMonitor configurations.
  - Verified 100% test pass rate with zero flaky tests.

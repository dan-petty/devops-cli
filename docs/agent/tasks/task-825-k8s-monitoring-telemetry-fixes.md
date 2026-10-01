# Task 825: Kubernetes Monitoring Telemetry Integration & Dashboard Metric Fixes

**Issue**: [#825](https://github.com/dan-petty/devops-cli/issues/825)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `scope/telemetry`, `priority/p1-high`

---

## 1. Description & Objectives

Resolves missing metrics and empty/zero-value panels across the Kubernetes Grafana dashboards (Views: Global, Namespaces, Pods, Nodes) and NVIDIA DCGM Exporter, and lets the Prometheus server scrape CoreDNS.

### Root Causes & Telemetry Vectors Addressed:
1. **NVIDIA DCGM Exporter Dashboard & GPU Metrics**:
   - The deployed `dcgm-exporter` ServiceMonitor had `interval: 15s` and default `scrapeTimeout: 25s`, causing Grafana Alloy to reject the scrape configuration (`scrape timeout greater than scrape interval`).
   - Pods on datacenter GPU nodes lacked `SYS_ADMIN` capability in the deployed release, leading to `Host engine is running as non-root` failures.
   - `k8s/monitoring/dcgm-exporter-values.yaml` already sets both (#738); the deployed release had drifted from it, so redeploying the infra stack fixes the cluster, and a test now pins the two values.
2. **Kubernetes Views (Global, Namespaces, Pods, Nodes)**:
   - `kube-state-metrics` omitted `metricLabelsAllowlist`, which defaulted to only allowing `nodes=[...]`. Consequently, `kube_namespace_labels`, `kube_deployment_labels`, `kube_statefulset_labels`, `kube_daemonset_labels`, `kube_hpa_labels`, and `kube_networkpolicy_labels` were never generated.
   - KSM active collectors lacked `endpoints`, preventing `kube_endpoint_info` from being emitted.
   - Alloy's cAdvisor and KSM allowlists dropped key operational metrics (`container_cpu_cfs_throttled_seconds_total`, `container_oom_events_total`, `container_network_receive_errors_total`, `container_network_transmit_errors_total`, `kube_hpa_labels`, `kube_pod_container_status_ready`, `kube_pod_container_status_last_terminated_exitcode`, `kube_pod_container_status_terminated`, `kube_pod_container_status_waiting`, `kube_deployment_status_replicas_unavailable`).
3. **Not in this item**:
   - The OpenTelemetry Collector is scraped through its pod annotations by the Prometheus server's `kubernetes-pods` job (#693). A ServiceMonitor would have Alloy scrape it a second time and double every collector series, so none is added.
   - Qdrant runs with an API key, so its scrape needs credentials, and no dashboard reads Qdrant since #693 removed the unverified row. The authenticated scrape and its dashboard row are #823.
4. **CoreDNS NetworkPolicy Egress**:
   - In `monitoring/networkpolicy.yaml`, egress to `kube-system` allowed port 53 (DNS) but omitted port 9153 (CoreDNS metrics endpoint). The `kube-dns` Service carries `prometheus.io/scrape: "true"` and `prometheus.io/port: "9153"`, so the Prometheus server's `kubernetes-service-endpoints` job tries to scrape CoreDNS, and the perimeter dropped it. The CoreDNS dashboard itself is #822.

---

### Key Deliverables Completed:
- [x] **Kubernetes Monitoring Stack Configuration** (`k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/monitoring/networkpolicy.yaml`):
  - Configured `telemetryServices.kube-state-metrics.metricLabelsAllowlist` for namespaces, deployments, statefulsets, daemonsets, horizontalpodautoscalers, networkpolicies, persistentvolumeclaims, pods, services, ingresses, and nodes.
  - Enabled `collectorsExtra: [endpoints]` in KSM to emit `kube_endpoint_info`.
  - Added missing container CFS throttling, OOM events, and network error metrics to `clusterMetrics.cadvisor.metricsTuning.includeMetrics`.
  - Added missing container status and workload label metrics to `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`.
  - Added port 9153 (TCP) to `monitoring-default-perimeter` NetworkPolicy egress to allow CoreDNS metrics scraping.
- [x] **Automated Regression Test Suite** (`tests/test_k8s_monitoring_integration.py`, `tests/test_k8s.py`):
  - Authored unit test assertions verifying cAdvisor and KSM metrics tuning, KSM metric labels allowlist, collectors extra, monitoring NetworkPolicy egress rules, the DCGM exporter's scrape timeout and capability, and that the OTel collector is scraped once, through its pod annotations, with no ServiceMonitor.
  - Verified 100% test pass rate with zero flaky tests.

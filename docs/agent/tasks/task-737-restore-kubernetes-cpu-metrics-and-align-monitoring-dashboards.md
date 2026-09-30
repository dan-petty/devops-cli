# Task 737: Restore Kubernetes CPU Metrics and Align Monitoring Dashboards to homelab-k3s

**Issue**: [#737](https://github.com/dan-petty/devops-cli/issues/737)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/k8s`, `priority/p1-high`

---

## 1. Description & Objectives

Grafana Kubernetes views dashboards (`Kubernetes / Views / Global`, `Kubernetes / Views / Nodes`, `Kubernetes / Views / Namespaces`, `Kubernetes / Views / Pods`) displayed "No Data" for total cluster CPU capacity, utilization, and requests/limits ratios. Additionally, monitoring metrics and dashboards were configured with the legacy cluster name `devops-cluster` instead of the active cluster `homelab-k3s`.

#### Key Deliverables:
- **cAdvisor Metric Whitelist**: Add `machine_cpu_cores` to `k8s-monitoring-values.yaml` under `clusterMetrics.cadvisor.metricsTuning.includeMetrics` so cluster capacity is exported.
- **Scrape Deduplication**: Disable redundant direct node and cAdvisor scraping in `prometheus-values.yaml` to prevent metric collisions and missing cluster labels.
- **Cluster Name Alignment**: Reconcile cluster naming from `devops-cluster` to `homelab-k3s` across Alloy values, Prometheus scrape post-relabel configs, and Grafana dashboard variables.
- **Dashboard Partitioning**: Split Kubernetes views dashboards into `k8s-global-dashboards-configmap.yaml` and `k8s-node-dashboards-configmap.yaml` to comply with the 256KB annotation limit.
- **PromQL Template Support**: Update PromQL static duration validator to allow Grafana template variables in range vectors.
- **Gateway Model Alignment**: Reconcile LiteLLM gateway routing model list in `configmap.yaml` with GPU matrix definitions and test fixtures.
- Unit and integration test coverage with structural tuple equality assertions.
- Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- 100% passing across Gated CI validation suite (`uv run devops ci`).

---

## 2. Verification Results

- `sum(machine_cpu_cores{cluster=~"homelab-k3s"})` evaluates to live capacity (96 cores).
- `sum(kube_pod_container_resource_requests{resource="cpu",cluster=~"homelab-k3s"}) / sum(machine_cpu_cores{cluster=~"homelab-k3s"}) * 100` evaluates to live utilization (~20.6%).
- `sum(kube_pod_container_resource_limits{resource="cpu",cluster=~"homelab-k3s"}) / sum(machine_cpu_cores{cluster=~"homelab-k3s"}) * 100` evaluates to live limits (~30.8%).
- All 42 dashboard linter tests in `tests/test_grafana_dashboards.py` pass.
- Gated CI quality gates (`uv run devops ci`) passing 100% across all 10 checks.

# Task: The Monitoring Stack Runs on k8s-monitoring and Chart Features (#1128)

**Issue**: [#1128](https://github.com/dan-petty/devops-cli/issues/1128)
**Scope**: scope/k8s, scope/telemetry
**Feasibility**: Confirmed against the cached `grafana/k8s-monitoring` 4.5.2 chart (`charts/feature-integrations/default-allow-lists/alloy.yaml` and `integrations/grafana-values.yaml`) and `k8s/monitoring/` values: `integrations.alloy` and `integrations.grafana` render Alloy discovery and scrape blocks with default allow lists, and `pyroscope-values.yaml` exposes `serviceMonitor.enabled`.

## Description
Parent issue #1128 consolidates the monitoring stack onto `grafana/k8s-monitoring` and native chart features without duplicate collection, dead defaults, or leftover resources. Children #1129 (`c213987d`), #1130 (`b7a3eb7f`), #1135 (`22f46809`), #823 (`40f25874`), and #1132 (`89eb129f`) have already landed.

### Part 1: Alloy Collectors, Grafana, and Pyroscope Scrapes and Pipeline Drop Alerts (#1131)
- `k8s/monitoring/k8s-monitoring-values.yaml` `integrations` adds two instances with their default allow lists:
  - `alloy`, named `k8s-monitoring`, with `labelSelectors: {app.kubernetes.io/name: [alloy-metrics, alloy-logs, alloy-singleton]}`;
  - `grafana`, named `grafana`.
- `k8s/monitoring/pyroscope-values.yaml` sets `serviceMonitor.enabled: true`.
- `k8s/monitoring/prometheus-values.yaml` adds the `homelab-telemetry-pipeline` rule group with two warning rules (`for: 15m`):
  - `AlloyRemoteWriteSamplesFailed`: `increase(prometheus_remote_storage_samples_failed_total{job="integrations/alloy"}[15m]) > 0`;
  - `AlloyLogEntriesDropped`: `increase(loki_write_dropped_entries_total{job="integrations/alloy"}[15m]) > 0`.
- `tests/fixtures/k8s_monitoring/integrations/alloy.yaml` checks in the `grafana/k8s-monitoring 4.5.2` default allow list for the Alloy integration with the chart version in its header.

### Part 2: Pod Log Shipper Liveness Alert (#890)
- `k8s/monitoring/prometheus-values.yaml` adds `PodLogsNotShipped` (`for: 30m`, `warning`) to `homelab-telemetry-pipeline`: alerts when an `alloy-logs` DaemonSet pod sends 0 entries to Loki over 5m for 30m, joining `node` from `kube_pod_info` so a node-maintenance silence covers it. (`PodLogsDropped` is superseded by #1131's `AlloyLogEntriesDropped`.)

## Acceptance Criteria
- [x] `k8s/monitoring/k8s-monitoring-values.yaml` `integrations` gains the `alloy` (`k8s-monitoring`) and `grafana` (`grafana`) instances.
- [x] `k8s/monitoring/pyroscope-values.yaml` sets `serviceMonitor.enabled: true`, and `test_prometheus_operator_crds_install_before_every_service_monitor` includes `("infra", "pyroscope")`.
- [x] `k8s/monitoring/prometheus-values.yaml` gains the `homelab-telemetry-pipeline` rule group with `AlloyRemoteWriteSamplesFailed`, `AlloyLogEntriesDropped`, and `PodLogsNotShipped`.
- [x] `tests/test_k8s_monitoring_alerting.py` asserts, as structural tuples, the pipeline drop rules and scrape settings (#1131) and `PodLogsNotShipped`'s name, expression, `for` duration, and severity (#890).
- [x] `tests/test_k8s_monitoring_alerting.py` asserts that every Alloy metric name the `homelab-telemetry-pipeline` rules use is in `tests/fixtures/k8s_monitoring/integrations/alloy.yaml` and that the fixture header matches the `k8s-monitoring` chart version pin in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- [x] `tests/test_k8s_monitoring_integration.py` `_scrape_owners` handles list-valued `labelSelectors` and chart-default `app.kubernetes.io/name` selectors.
- [x] `k8s/README.md` documents the Alloy, Grafana, and Pyroscope scrapes and the new alerts.
- Remaining children of #1128 delivered in subsequent PRs: #1133, #1134, #822, #1136, #551, and #1367.
- Pending a person, after the infra stack is redeployed:
  - `count by (job) (up{job=~"integrations/alloy|integrations/grafana|.*pyroscope.*"})` shows 3 Alloy targets (4 before #1134), 1 Grafana and 1 Pyroscope;
  - `sum by (pod) (loki_write_sent_entries_total)` returns one row per `alloy-logs` pod and `alloy-singleton`;
  - `AlloyRemoteWriteSamplesFailed` and `PodLogsNotShipped` stay inactive on a healthy cluster.

# Task: k8s-monitoring Collectors Run in the Chart's Preset Shapes, and node-exporter Keeps the Series the Node Dashboards Read (#1129)

**Issue**: [#1129](https://github.com/dan-petty/devops-cli/issues/1129)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p1-high
**Scope**: scope/k8s, scope/telemetry

## Description
Four settings in `k8s/monitoring/k8s-monitoring-values.yaml` (k8s-monitoring 4.5.2) did not do what the file said. Each fix uses a chart feature that already exists:

1. **node-exporter has no allow list.** The chart's `_linux_hosts.alloy.tpl` concatenates the default list (on unless `useDefaultAllowList` is `false`), the integration list (only when `useIntegrationAllowList` is `true`) and `includeMetrics`, and renders the `keep` rule only when that list is non-empty. The flag flipped in three releases (v0.2.24, v0.2.25, v0.2.26), and each time a different set of Node Exporter Full and Kubernetes node dashboard panels went empty; the integration list still dropped 38 names the dashboard reads that node-exporter serves. `metricsTuning` now sets `useDefaultAllowList: false` and `useIntegrationAllowList: false` with no `includeMetrics`, so no keep rule is rendered and Prometheus keeps every series node-exporter serves. node-exporter's collector flags (`telemetryServices.node-exporter.extraArgs`) remain the one place that decides what is collected, and the chart's ramfs/tmpfs filesystem drop stays. The #1080 host-failure series come through because node-exporter serves them, with the systemd collector #1080 turned on.
2. **`alloy-singleton` is a singleton.** The collector had no `presets`, so the Alloy chart's default made it a DaemonSet with one pod per node, each running `loki.source.kubernetes_events` and shipping the whole event stream. `clusterEvents` runs unclustered, and the chart says it then "should run on a singleton collector". `collectors.alloy-singleton.presets: [singleton]` makes it a one-replica Deployment.
3. **The cluster name is written once.** The chart's prometheus destination defaults to `clusterLabels: [cluster, k8s.cluster.name]`, so every Alloy-written series carried both `cluster` and `k8s_cluster_name`. Dashboards and rules key on `cluster` only; `destinations.localPrometheus.clusterLabels: [cluster]` drops the duplicate.
4. **`kube_hpa_labels` leaves the kube-state-metrics allow list.** It is a kube-state-metrics v1 name that v2 never serves; the chart's default KSM list already carries `kube_horizontalpodautoscaler_*`. The dashboards that still query it are fixed in #1136.

`destinations.localLoki` keeps the chart's default `clusterLabels`, so Loki streams still carry `k8s_cluster_name`; the item is scoped to the Prometheus destination.

## Acceptance Criteria
- [x] `hostMetrics.linuxHosts.metricsTuning` sets `useDefaultAllowList: false` and `useIntegrationAllowList: false` and has no `includeMetrics`, with a comment saying that node-exporter's collector flags (`telemetryServices.node-exporter.extraArgs`) decide what is collected and why there is no allow list. `test_host_metrics_keep_the_series_that_explain_a_host_failure` rebuilds the keep sources the way `_linux_hosts.alloy.tpl` concatenates them (default list unless `useDefaultAllowList` is false, integration list when `useIntegrationAllowList` is true, then `includeMetrics`), without the lists' contents, and asserts they are empty alongside the unchanged node-exporter arguments and D-Bus address. No list fixture is checked in.
- [x] Review mutation: removing `useDefaultAllowList: false` (the chart default is `true`) fails `test_host_metrics_keep_the_series_that_explain_a_host_failure` with keep sources `['default']`.
- [x] `collectors.alloy-singleton.presets: [singleton]`. `test_each_alloy_collector_runs_in_one_controller_preset` asserts, as one tuple, that each collector names exactly one of the controller presets `singleton`, `daemonset`, `statefulset` and `deployment`, and that the `clusterEvents` collector uses `singleton` while `clusterEvents.clustering` is unset or false.
- [x] Review mutation: removing `presets` from `alloy-singleton` fails `test_each_alloy_collector_runs_in_one_controller_preset`.
- [x] `destinations.localPrometheus.clusterLabels: [cluster]`, pinned by `test_alloy_writes_the_cluster_name_once`; deleting the line fails it.
- [x] `kube_hpa_labels` is removed from the KSM `includeMetrics`. The refinement of 2026-10-08 replaced the criterion that expected `True` at both places pinning the allow-list flag: `test_k8s_monitoring_cadvisor_and_ksm_metrics_tuning` no longer reads `useIntegrationAllowList` or requires `kube_hpa_labels`, and the host-metrics test asserts both flags off with no `includeMetrics`.
- [x] The LiteLLM and DCGM exporter capture fixtures (`tests/fixtures/metrics/litellm.yaml`, `dcgm-exporter.yaml`) drop `k8s_cluster_name` from their Alloy target labels; `tests/test_stack_dashboards.py` passes against them.
- [x] No test reaches the network or runs `helm`. Each new or changed test's call phase is 0.01 s (`uv run pytest tests/test_k8s_monitoring_integration.py --durations=10`).
- [x] `changelog.d/1129.md` exists; `CHANGELOG.md` and `docs/ROADMAP.md` are untouched.
- [x] Review render, outside the gate: `helm template` of the k8s-monitoring 4.5.2 chart with the previous and the new values differs in exactly four hunks: `kube_hpa_labels` leaves the KSM keep regex; the `node_exporter` keep rule is gone (the ramfs/tmpfs drop rule stays); `k8s_cluster_name` leaves the `prometheus.remote_write "localprometheus"` external labels; the `alloy-singleton` Alloy resource gains `type: deployment` and `replicas: 1`.
- Pending a person, after the v0.2.32 release PR merges into main and Argo CD syncs the `k8s-monitoring` Application (it tracks main with selfHeal, so do not apply early with `devops k8s deploy-stack` from the release branch: Argo CD would revert it):
  1. `kubectl get application -n argocd k8s-monitoring -o jsonpath='{.status.sync.status} {.status.sync.revisions}'` prints `Synced ["4.5.2","<new main sha>"]`.
  2. `kubectl get alloys.collectors.grafana.com -n monitoring k8s-monitoring-alloy-singleton -o jsonpath='{.spec.controller.type} {.spec.controller.replicas}'` prints `deployment 1`.
  3. `kubectl get deploy,ds -n monitoring | grep alloy-singleton` shows only `deployment.apps/k8s-monitoring-alloy-singleton 1/1`, and no DaemonSet of that name.
  4. `kubectl get endpointslices -n monitoring -l kubernetes.io/service-name=k8s-monitoring-alloy-singleton -o jsonpath='{range .items[*].endpoints[*]}{.addresses[0]}{"\n"}{end}' | wc -l` prints `1`, so the events Ingress reaches one Alloy UI.
  5. Ten minutes later, in Grafana Explore against Prometheus: `count(node_uname_info)` equals the node count; `count by (__name__) ({__name__=~"node_load1|node_context_switches_total|node_netstat_Tcp_CurrEstab|node_disk_io_now"})` returns all four names; `count by (__name__) ({__name__=~"node_procs_blocked|node_forks_total|node_scrape_collector_success|node_systemd_units", job="integrations/node_exporter"})` returns all four names; `count({k8s_cluster_name!=""})` is empty (the issue's `count_over_time` form errors on duplicate labelsets).
  6. Node Exporter Full shows data on every node, except the processes, interrupts and TCP connection-state panels (collectors off by default) and panels for hardware a node lacks.

## Deliverables
- [x] `k8s/monitoring/k8s-monitoring-values.yaml`: no node-exporter allow list, `alloy-singleton` on the `singleton` preset, `clusterLabels: [cluster]` on the Prometheus destination, `kube_hpa_labels` removed.
- [x] `tests/test_k8s_monitoring_integration.py`: the host-metrics and cAdvisor/KSM tests rewritten; `test_each_alloy_collector_runs_in_one_controller_preset` and `test_alloy_writes_the_cluster_name_once` added.
- [x] `tests/fixtures/metrics/litellm.yaml`, `tests/fixtures/metrics/dcgm-exporter.yaml`: `k8s_cluster_name` removed from the target labels.
- [x] `tests/test_k8s_monitoring_alerting.py`: the node-exporter comment says where the series come from now.
- [x] `k8s/README.md` "Host Journals and Health Metrics": host metrics have no allow list.
- [x] Task files #1080, #1175 and #693 note what changed since #1129.
- [x] `changelog.d/1129.md`.

# Task: The Prometheus Server Scrapes Only Itself and the OTel Collector, and k8s-monitoring Discovers Every Other Target (#1130)

**Issue**: [#1130](https://github.com/dan-petty/devops-cli/issues/1130)
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p1-high
**Scope**: scope/k8s, scope/telemetry
**Feasibility**: Confirmed against the live cluster read-only on 2026-10-09 (kubectl get, Prometheus queries through Grafana): the API-server job held 59,700 of 99,544 head series, 1,375 series lacked a cluster label (all from the self-scrape), and every Argo CD app was Synced; the chart values read at origin/release/v0.2.33 still enabled the four extra scrape jobs this change removes.

## Description
The cluster had two scrapers. Alloy, run by k8s-monitoring 4.5.2, scraped the kubelet, cAdvisor, kube-state-metrics, node-exporter, DCGM and the llm gateway. The prometheus-community server (chart 29.35.0) ran its own Kubernetes discovery beside it, mostly with chart-default jobs. The API-server job held about 60% of the head series (59,700 of 99,602 on 2026-10-09) and nothing read them; four jobs matched nothing; the cluster name was a literal in five relabel blocks, and the server's self-scrape carried no `cluster` at all.

The server now runs two jobs: its self-scrape and `kubernetes-pods`, which keeps only namespace `otel`, so the collector's export failures stay visible when Alloy is what fails. Both take their cluster relabel from one YAML anchor. k8s-monitoring takes over every other target with chart features:

- **Annotation autodiscovery** finds cloudflared, Traefik, Alertmanager and roadmap-service through the `prometheus.io/*` annotations they already carry. It skips `otel`, leaves Service discovery off and sends no ServiceAccount token.
- **`clusterMetrics.kubeDNS`** scrapes CoreDNS, which the server's service-endpoints job scraped before.
- **The Loki integration** selects Loki's single-binary pod by its labels, so Loki's pod annotations are gone.
- **The dcgm-exporter integration** scrapes the exporter every 15s, so the chart's own ServiceMonitor is off.

Autodiscovery, kube-dns and DCGM each carry a discovery rule that copies the pod's node to `node`, which the node-maintenance silence and the NodeNotReady inhibition match. `k8s/README.md` gains a Scrape Ownership section with a table of the monitoring components that run outside k8s-monitoring, and why.

Deviations from the issue text:
- **Loki's job is `logging/single-binary`, not `integrations/loki`.** The integration sets `job` to namespace/component for the loki-mixin. It also moves `node` into `instance` and drops `node`, so a Loki `TargetDown` is named by `instance`, which is the node.
- **`annotationAutodiscovery.bearerToken.enabled: false`.** The chart sends the ServiceAccount token to every annotated pod by default, over plain HTTP. No annotated target needs it.
- **Alertmanager carries `k8s.grafana.com/metrics.container: alertmanager`.** Autodiscovery makes one target per container. It would rewrite the config-reloader sidecar's target to the annotated port 9093, so Alertmanager would be scraped twice.
- **roadmap-service is a seventh annotated workload.** The issue lists six; autodiscovery finds it like the others.
- **`clusterMetrics.kubeDNS.extraDiscoveryRules` carries the node rule.** The server's service-endpoints job set `node` on CoreDNS. Without the rule, a CoreDNS `TargetDown` would fall back to the pod address, and the node silence would not cover it.
- **The Loki instance sets `logs.enabled: false`.** The item changes metrics only, and Loki's own pod logs stay as `podLogsViaLoki` ships them.
- **DCGM series lose labels.** They no longer carry the exporter pod's `container`, `endpoint`, `namespace`, `pod` and `service` labels. Nothing reads them: `llm-stack.json` uses `hostname`, `gpu` and `modelName`, dashboard 12239 uses `instance` and `gpu`, and the GPU rules use `node` and `gpu`.
- **Only Loki's integration has an allow list.** The issue expected chart allow lists on Loki, CoreDNS and DCGM. k8s-monitoring 4.5.2 has a default list for Loki only; kube-dns, DCGM and autodiscovery forward every series their targets serve.
- **Traefik is managed by Argo CD.** The issue calls it k3s-managed, but `k8s/argocd/apps/traefik.yaml` installs it in `kube-system`, and the chart sets its `prometheus.io/*` annotations.
- **The dcgm-exporter Application drops `SkipDryRunOnMissingResource`.** The chart no longer renders a ServiceMonitor, so the option has nothing left to skip. `dcgm-exporter-values.yaml` keeps only `serviceMonitor.enabled: false`, because the chart's default is on.
- **The expected drop is about 60k head series.** The issue said 50k; that figure is re-measured live.

## Acceptance Criteria
- [x] `k8s/monitoring/prometheus-values.yaml` sets `enabled: false` on `kubernetes-api-servers`, `kubernetes-service-endpoints`, `kubernetes-service-endpoints-slow`, `kubernetes-pods-slow`, `kubernetes-services` and `prometheus-pushgateway`, with their relabel blocks deleted. `kubernetes-nodes` and `kubernetes-nodes-cadvisor` stay off.
- [x] `kubernetes-pods` stays enabled, and its `pre_relabel_configs` keep only namespace `otel`. Its comment cites the README's independence reason.
- [x] `prometheus` and `kubernetes-pods` take their cluster relabel from one anchor (`&cluster`). The self-scrape carries `cluster`.
- [x] `annotationAutodiscovery` is set as follows:
  - `enabled: true`, `collector: alloy-metrics`;
  - the `prometheus.io/scrape`, `prometheus.io/port` and `prometheus.io/path` annotation keys;
  - `excludeNamespaces: [otel]`, `services.enabled: false` and `bearerToken.enabled: false`;
  - the node rule in `extraDiscoveryRules`.
- [x] `clusterMetrics.kubeDNS.enabled: true`, with the same node rule.
- [x] `integrations.collector: alloy-metrics`, with two instances:
  - `loki`: `labelSelectors` `{app.kubernetes.io/name: loki, app.kubernetes.io/component: single-binary}`, the chart's default allow list, and `logs.enabled: false`;
  - `dcgm-exporter`: `labelSelectors` `{app.kubernetes.io/name: dcgm-exporter}`, `metrics.scrapeInterval: 15s`, and discovery rules that set `node` and `instance` from `__meta_kubernetes_pod_node_name`.
- [x] `k8s/logging/loki-values.yaml` sets no `podAnnotations`. `k8s/monitoring/dcgm-exporter-values.yaml` sets `serviceMonitor: {enabled: false}` and nothing else under it.
- [x] `test_scrape_ownership_moves_to_k8s_monitoring` asserts all of the above as one tuple, including Alertmanager's three annotations. The enabled server jobs are computed over the 10 default jobs in prometheus 29.35.0's `values.yaml` (`PROMETHEUS_DEFAULT_JOBS`), so a default job that the values leave out counts as on.
- [x] `test_each_annotated_component_has_one_scrape_owner` asserts exactly one owner for each of cloudflared, roadmap-service, Alertmanager, the collector, Loki and DCGM. The owners are the server's `kubernetes-pods` job, autodiscovery, each integration instance, and the DCGM chart's own ServiceMonitor. `test_a_component_with_no_scrape_owner_or_two_fails` runs the four review mutations, and each one fails the check:
  - Alertmanager without its scrape annotation;
  - the collector without its annotations;
  - `otel` removed from `excludeNamespaces`;
  - Loki annotated again.
- [x] `test_every_scrape_port_has_one_egress_rule` counts the egress rules in `k8s/monitoring/networkpolicy.yaml` for each scrape port, using one counting helper, `_egress_rules_to`. Each port has exactly one rule: cloudflared 2000, devops 8000, `kube-system` 9100 (Traefik) and 9153 (CoreDNS), logging 3100, monitoring 9093 and 9400, and otel 8888. The policy needed no change.
- [x] `tests/test_stack_dashboards.py` reads the new owners:
  - `_dcgm_monitored` reads the k8s-monitoring dcgm-exporter integration;
  - `_collector_annotated` also requires the server job to keep namespace `otel`.

  The DCGM and Prometheus server capture fixtures name their new scrapes and target labels. No test compares the DCGM job label.
- [x] `k8s/README.md` has a Scrape Ownership section. Its table has one row for each of the eight components, with the owner and the reason, and the lines after it name the autodiscovered pods and what `devops prometheus targets` lists. The dashboard table, Log and Metric Retention, `LokiRetentionNotRunning`, Planned maintenance (where `node` comes from, and what stops with `alloy-metrics-0`) and the directory listing describe the new owners.
- [x] No test reaches the network or runs `helm`. Each new test's call phase is at most 0.02 s (`uv run pytest tests/test_k8s_monitoring_integration.py --durations=0`). `changelog.d/1130.md` exists; CHANGELOG.md and docs/ROADMAP.md are untouched.
- [x] Review render, outside the gate: `helm template` of the cached k8s-monitoring 4.5.2 and prometheus 29.35.0 charts with the new values.
  - The k8s-monitoring render only adds Alloy configuration. The autodiscovery scrape has no `bearer_token_file`.
  - The node rule renders in `annotation_autodiscovery_pods`, `kube_dns` and the DCGM instance. DCGM's `scrape_interval` is `"15s"`, and no Loki log rule renders.
  - `prometheus.yml` has only the `kubernetes-pods` job, whose first rule keeps `otel`, and the `prometheus` job. Both end with the `cluster` replace rule.
- Pending a person, after the v0.2.33 release PR merges into main and Argo CD syncs the `prometheus`, `k8s-monitoring`, `dcgm-exporter` and `loki` Applications. They track main, so do not apply early with `devops k8s deploy-stack` from the release branch: Argo CD would revert it.
  1. `kubectl get application -n argocd prometheus k8s-monitoring dcgm-exporter loki -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REV:.status.sync.revisions` shows each one `Synced` and `Healthy` at the merge commit.
     - `kubectl get servicemonitor -A` lists only `llm/llm-gateway`.
     - `kubectl -n logging get pod loki-0` and `kubectl -n monitoring get pod prometheus-alertmanager-0` show pods restarted since the sync, because their pod template annotations changed.
     - In Grafana Explore against Prometheus, `prometheus_config_last_reload_successful` is `1`.
  2. Fifteen minutes later, `count by (job) (up)` returns these jobs and no others besides the unchanged Alloy jobs (kubelet, cAdvisor, resources, kube-state-metrics, node_exporter, llm-gateway):
     - `prometheus` 1 and `kubernetes-pods` 1;
     - `cloudflared` 2, `traefik` 1, `alertmanager` 1 and `roadmap-service` 1;
     - `integrations/kubernetes/kube-dns`, equal to the CoreDNS pods in `kubectl -n kube-system get pods -l k8s-app=kube-dns`;
     - `logging/single-binary` 1;
     - `integrations/dcgm-exporter`, equal to the GPU nodes in `kubectl get nodes -l nvidia.com/gpu.present=true`.

     No `kubernetes-api-servers`, `kubernetes-service-endpoints` or `dcgm-exporter` job is left.
  3. `count(alertmanager_build_info)` is `1`, so Alertmanager is scraped once.
  4. `count by (job) (up{node=""})` lists only `prometheus`, `llm-gateway`, `integrations/kubernetes/kube-state-metrics`, `integrations/node_exporter` and `logging/single-binary`.
  5. `count by (node, gpu) (DCGM_FI_DEV_GPU_TEMP)` equals the number of GPUs, and the instance variable of dashboard 12239 lists node names.
  6. `loki_compactor_apply_retention_last_successful_run_timestamp_seconds` and `coredns_dns_requests_total` each return series.
  7. `count({__name__=~".+", __name__!~"ALERTS.*", cluster=""})` is empty.
  8. `ALERTS{alertname="TargetDown"}` holds no alert for the new jobs.
  9. Three hours later, `prometheus_tsdb_head_series` is about 60k lower than before the sync (about 99.6k on 2026-10-09).

## Deliverables
- [x] `k8s/monitoring/prometheus-values.yaml`:
  - two scrape jobs, with one cluster anchor;
  - the six chart-default jobs off;
  - Alertmanager's container annotation;
  - the scrape and `LokiRetentionNotRunning` comments rewritten.
- [x] `k8s/monitoring/k8s-monitoring-values.yaml`: `clusterMetrics.kubeDNS`, `annotationAutodiscovery`, and `integrations` with the Loki and DCGM instances. The block stays a plain instance list, so #1131 only appends.
- [x] `k8s/logging/loki-values.yaml`: the pod annotations removed.
- [x] `k8s/monitoring/dcgm-exporter-values.yaml`: the ServiceMonitor off. `k8s/argocd/apps/dcgm-exporter.yaml`: `SkipDryRunOnMissingResource` removed.
- [x] `k8s/monitoring/prometheus-operator-crds-values.yaml` and the `stack_lifecycle.py` release comment: only k8s-monitoring's extraObjects render ServiceMonitors.
- [x] `k8s/monitoring/dashboards/prometheus-server.json`: the "Scrape Duration by Job" description names the jobs that forward `scrape_duration_seconds`.
- [x] `tests/test_k8s_monitoring_integration.py`:
  - the ownership, single-owner, mutation and egress-count tests;
  - the DCGM test rewritten;
  - `_has_egress_port_to_namespace` replaced by `_egress_rules_to`.
- [x] Other test updates:
  - `tests/test_stack_dashboards.py` and the DCGM and Prometheus server capture fixtures;
  - `tests/test_k8s_monitoring_alerting.py`: the `SERVED_SERIES` comments, and `test_k8s_monitoring_scrapes_loki_and_alertmanager_for_their_health`;
  - `tests/test_k8s.py`: the ServiceMonitor release tuple;
  - `tests/test_llm_pool_metrics.py`: the DCGM ServiceMonitor flag.
- [x] `k8s/README.md`: the Scrape Ownership section, and the stale lines rewritten.
- [x] Task files #549, #693, #819, #825, #935 and #1485 note what changed since #1130.
- [x] `changelog.d/1130.md`.
- Follow-ups, not in this item:
  - #1131 appends the Alloy, Grafana and Pyroscope integrations;
  - #822 keeps the CoreDNS dashboard;
  - #823 keeps the CRDs and `prometheusOperatorObjects` for the Qdrant monitor;
  - #1132 keeps the collector on the server.

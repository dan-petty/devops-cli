# Task: The Monitoring Stack Runs on k8s-monitoring and Chart Features (#1128)

**Issue**: [#1128](https://github.com/dan-petty/devops-cli/issues/1128)
**Scope**: scope/k8s, scope/telemetry
**Feasibility**: Confirmed against the cached `grafana/k8s-monitoring` 4.5.2 chart (`charts/feature-integrations/default-allow-lists/alloy.yaml`, `integrations/grafana-values.yaml`, and `helm template` of `profiling` + `destinations.localPyroscope`), `k8s/monitoring/` values, live `monitoring` pod labels (`app.kubernetes.io/name` and `app.kubernetes.io/instance`), live cluster node BTF support (`/sys/kernel/btf/vmlinux` present on all nodes), live Pyroscope `/metrics` (`pyroscope_request_duration_seconds_count{route,status_code}`), and Loki 3.6.11 (`grafana/loki` chart 7.3.0 `appVersion`) upstream Go source (`pkg/loki/modules.go:595, 708, 1167-1194`, `pkg/compactor/generationnumber/gennumber_loader.go:106-126`, `pkg/compactor/deletion/grpc_request_handler.go:63-85`).

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

### Part 3: Loki Canary, Pyroscope Log Level, Grafana Sidecar Scoping, and Loki Ingress Peers (#1133)
- `k8s/logging/loki-values.yaml` sets `lokiCanary.enabled: false` (pipeline liveness is covered by Alloy's `loki_write_sent_entries_total` in #1131 and #890) and documents the upstream Loki 3.6.11 bug (`grafana/loki#8468`, `grafana/loki#9855`) on `limits_config.deletion_mode: disabled`: `initQuerier` (`pkg/loki/modules.go:595, 708`) attaches `CacheGenNumberHeaderSetterMiddleware` whenever `store: tsdb` and `compactor.retention_enabled: true`, and `initCacheGenerationLoader` (`pkg/loki/modules.go:1167-1194`) passes an unwrapped gRPC client to `NewGenNumberLoader` instead of `NewPerTenantDeleteRequestsClient`, so `/grpc.Compactor/GetCacheGenNumbers` logs `deletion is not available for this tenant` on queries while `deletion_mode` is `disabled`.
- `k8s/logging/networkpolicy.yaml` replaces the namespace-only `monitoring` peer on TCP 3100 with combined `namespaceSelector` + `podSelector` peers for Grafana (`grafana`/`grafana`) and the three `k8s-monitoring` Alloy collectors (`alloy-logs`, `alloy-metrics`, `alloy-singleton`).
- `k8s/monitoring/pyroscope-values.yaml` sets `pyroscope.extraArgs.log.level: info` (overriding the chart's `debug` default).
- `k8s/monitoring/grafana-values.yaml` sets `sidecar.datasources.enabled: false`, `sidecar.dashboards.searchNamespace: monitoring`, `sidecar.dashboards.resource: configmap`, and `rbac.namespaced: true`.

### Part 4: Profiling via k8s-monitoring `alloy-profiles`, Dashboard Variable Fixes, and `PyroscopeQueryErrors` Alert (#1134)
- `k8s/monitoring/pyroscope-values.yaml` sets `alloy.enabled: false` and removes the bundled subchart settings.
- `k8s/monitoring/k8s-monitoring-values.yaml` adds `destinations.localPyroscope` (`type: pyroscope`, `url: http://pyroscope.monitoring.svc.cluster.local:4040`), `profiling` (`enabled: true`, `collector: alloy-profiles`, `ebpf: {enabled: true, targetingScheme: all}`, `pprof: {enabled: true}`), and `collectors.alloy-profiles` (`presets: [daemonset, privileged]`, `alloy.enableReporting: false`, `resources`). Kernel BTF (`/sys/kernel/btf/vmlinux`) is verified present on every cluster node.
- `k8s/monitoring/dashboards/pyroscope.json` replaces its hard-coded custom `$service` list with a Pyroscope `label_values(service_name)` query, and `k8s/monitoring/dashboards/sre-service.json` replaces `created_by_name` with Pyroscope `label_values({service_namespace="$namespace"}, service_name)` and selects flamegraphs by `{service_namespace="$namespace", service_name=~"$service"}`.
- `k8s/monitoring/prometheus-values.yaml` adds `PyroscopeQueryErrors` (`sum by (route) (rate(pyroscope_request_duration_seconds_count{status_code=~"5.."}[15m])) > 0`, `for: 15m`, `warning`) to `monitoring-self`.

### Part 5: CoreDNS Dashboard and Metric Capture (#822)
- Verified on the live cluster that `up{job="integrations/kubernetes/kube-dns"}` returns `1` (`service="kube-dns"`, `namespace="kube-system"`) and `sum(rate(coredns_dns_requests_total[5m]))` returns `1.97`, and that all five CoreDNS dashboard queries return live data.
- `tests/fixtures/metrics/coredns.yaml` captures the metric families, types, and label names served by `rancher/mirrored-coredns-coredns:1.12.0` on `kube-dns.kube-system.svc.cluster.local:9153/metrics`.
- `k8s/monitoring/dashboards/coredns.json` (`uid: devops-coredns`, provisioned via `grafana-stack-dashboards` in `k8s/monitoring/dashboards/kustomization.yaml`) adds panels for requests by type and protocol, responses by rcode, request duration (p50/p95/p99), forward request duration (p50/p95/p99), and cache hits and misses.
- `tests/test_stack_dashboards.py` registers `coredns` in `EXPORTERS` and `coredns.json` in `DASHBOARD_EXPORTERS`.

### Part 6: Stack Dashboard Queries Match Exported Metrics and Capture Verification (#1136)
- `k8s/monitoring/dashboards/ingress-tunnel.json` removes `Cloudflare Service Status` (already on `project-metrics.json`), replaces `traefik_entrypoint_open_connections` with `sum by (entrypoint) (traefik_open_connections{entrypoint=~"$entrypoint"})`, and replaces `traefik_service_open_connections` with `sum by (service) (rate(traefik_service_requests_total{service=~"$service"}[$__rate_interval]))` (`Per-Service Request Rate`).
- `k8s/monitoring/dashboards/k8s-views-global.json` and `k8s/monitoring/dashboards/k8s-views-namespaces.json` replace `kube_hpa_labels` with `kube_horizontalpodautoscaler_labels`, and `k8s/monitoring/k8s-monitoring-values.yaml` adds `kube_horizontalpodautoscaler_labels` to `clusterMetrics.kube-state-metrics.metricsTuning.includeMetrics`.
- `k8s/monitoring/dashboards/k8s-views-namespaces.json` drops the `pod=~"${created_by}.*"` matcher from `kube_deployment_status_replicas_unavailable`, and both `k8s-views-namespaces.json` and `k8s-views-nodes.json` remove the `kubelet_volume_stats_*` PersistentVolume panels (omitted because `local-path` reports no volume stats) and note this in their dashboard descriptions.
- `k8s/monitoring/dashboards/k8s-views-nodes.json` plots the gauge `node_disk_io_now` directly instead of wrapping it in `rate(...[$__rate_interval])`.
- `k8s/monitoring/dashboards/otel-collector.json` sets `fieldConfig.defaults.noValue: "none recorded"` on `"Spans Sent and Failed per Exporter"`.
- `tests/fixtures/k8s_monitoring/cluster_metrics/` checks in the `grafana/k8s-monitoring 4.5.2` default allow lists for `cadvisor`, `kube-state-metrics`, and `kubelet`, and `tests/fixtures/metrics/` adds live metric captures for `traefik`, `cloudflared`, `kube-state-metrics`, `node-exporter`, `kubelet`, and `cadvisor`. `tests/test_stack_dashboards.py` filters `cadvisor`, `kube-state-metrics`, and `kubelet` captures by the effective allow list and registers `ingress-tunnel.json`, `k8s-views-global.json`, `k8s-views-namespaces.json`, and `k8s-views-nodes.json` in `DASHBOARD_EXPORTERS`.

### Part 7: Argo CD, Valkey, and Registry Scrapes and Service Health Alerts (#551)
- `k8s/argocd/values.yaml` enables `metrics.enabled: true` and `metrics.serviceMonitor.enabled: true` on `controller` (port 8082), `server` (port 8083), `repoServer` (port 8084), and `redis` (port 9121, with `redis.exporter.enabled: true` running `ghcr.io/oliver006/redis_exporter:v1.93.0`), and `k8s/argocd/networkpolicy.yaml` admits TCP 8083 from `monitoring` alongside 8082, 8084, and 9121.
- `k8s/llm/valkey.yaml` adds a hardened `redis-exporter` sidecar (`ghcr.io/oliver006/redis_exporter:v1.93.0`, port 9121) and `prometheus.io/*` + `k8s.grafana.com/metrics.container: redis-exporter` pod annotations for `annotationAutodiscovery`.
- `k8s/registry/deployment.yaml` enables Distribution's Prometheus debug endpoint (`REGISTRY_HTTP_DEBUG_ADDR=0.0.0.0:5001`, `REGISTRY_HTTP_DEBUG_PROMETHEUS_ENABLED=true`) with `prometheus.io/*` pod annotations for `annotationAutodiscovery`.
- `k8s/monitoring/networkpolicy.yaml` adds egress rules from `monitoring` to `argocd` (TCP 8082, 8083, 8084, 9121), `llm` (TCP 9121), and `registry` (TCP 5001), verified by `test_each_annotated_component_has_one_scrape_owner` and `test_every_scrape_port_has_one_egress_rule`.
- `k8s/monitoring/prometheus-values.yaml` adds the `homelab-services` rule group (`ArgoCdApplicationOutOfSync`, `ArgoCdApplicationUnhealthy`, `CloudflareTunnelDegraded`, and `ValkeyCacheErrors`).

## Acceptance Criteria
- [x] `k8s/monitoring/k8s-monitoring-values.yaml` `integrations` gains the `alloy` (`k8s-monitoring`) and `grafana` (`grafana`) instances.
- [x] `k8s/monitoring/pyroscope-values.yaml` sets `serviceMonitor.enabled: true`, and `test_prometheus_operator_crds_install_before_every_service_monitor` includes `("infra", "pyroscope")`.
- [x] `k8s/monitoring/prometheus-values.yaml` gains the `homelab-telemetry-pipeline` rule group with `AlloyRemoteWriteSamplesFailed`, `AlloyLogEntriesDropped`, and `PodLogsNotShipped`.
- [x] `tests/test_k8s_monitoring_alerting.py` asserts, as structural tuples, the pipeline drop rules and scrape settings (#1131) and `PodLogsNotShipped`'s name, expression, `for` duration, and severity (#890).
- [x] `tests/test_k8s_monitoring_alerting.py` asserts that every Alloy metric name the `homelab-telemetry-pipeline` rules use is in `tests/fixtures/k8s_monitoring/integrations/alloy.yaml` and that the fixture header matches the `k8s-monitoring` chart version pin in `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- [x] `tests/test_k8s_monitoring_integration.py` `_scrape_owners` handles list-valued `labelSelectors` and chart-default `app.kubernetes.io/name` selectors.
- [x] `k8s/README.md` documents the Alloy, Grafana, and Pyroscope scrapes and the new alerts.
- [x] `k8s/logging/loki-values.yaml` sets `lokiCanary.enabled: false` and documents the Loki 3.6.11 `GetCacheGenNumbers` behavior with `deletion_mode: disabled` and `compactor.retention_enabled: true`.
- [x] `k8s/logging/networkpolicy.yaml` narrows the `monitoring` ingress peer on TCP 3100 to Grafana and the three `k8s-monitoring` Alloy collectors, and `tests/test_k8s_network_policies.py` pins the peer set and rejects a namespace-only `monitoring` peer.
- [x] `k8s/monitoring/pyroscope-values.yaml` sets `pyroscope.extraArgs.log.level: info` and `k8s/monitoring/grafana-values.yaml` disables the datasource sidecar and scopes the dashboard sidecar and RBAC to `monitoring` ConfigMaps, verified by structural tuple and debug-log-level tests in `tests/test_k8s_monitoring_integration.py`.
- [x] `k8s/monitoring/pyroscope-values.yaml` disables the bundled Alloy subchart (`alloy.enabled: false`) and `k8s/monitoring/k8s-monitoring-values.yaml` configures `destinations.localPyroscope`, `profiling` (`ebpf.targetingScheme: all` and `pprof`), and `collectors.alloy-profiles`.
- [x] `k8s/monitoring/dashboards/pyroscope.json` and `k8s/monitoring/dashboards/sre-service.json` query `service_name` from Pyroscope without hard-coded service lists or `created_by_name`, and `k8s/monitoring/prometheus-values.yaml` adds `PyroscopeQueryErrors`.
- [x] `k8s/monitoring/dashboards/coredns.json` and `tests/fixtures/metrics/coredns.yaml` add the CoreDNS dashboard over captured `coredns_*` series (`job="integrations/kubernetes/kube-dns"`), verified by `tests/test_stack_dashboards.py` and `tests/test_k8s_monitoring_dashboards.py`.
- [x] `ingress-tunnel.json`, `k8s-views-global.json`, `k8s-views-namespaces.json`, `k8s-views-nodes.json`, and `otel-collector.json` queries match exported series and labels, verified against `tests/fixtures/metrics/` and `tests/fixtures/k8s_monitoring/cluster_metrics/` in `tests/test_stack_dashboards.py` (#1136).
- [x] Argo CD (`ServiceMonitor`s for `controller`, `server`, `repoServer`, and `redis-exporter`), `llm/valkey` (`redis-exporter` sidecar via `annotationAutodiscovery`), and `registry` (`annotationAutodiscovery` on port 5001) have exactly one scrape owner and one monitoring egress rule per port, and `homelab-services` alerts on Argo CD sync/health, tunnel HA connections, and Valkey cache errors (#551).
- Remaining child of #1128 delivered in the final PR: #1367.
- Pending a person, after the infra and logging stacks are redeployed:
  - `count by (job) (up{job=~"integrations/alloy|integrations/grafana|.*pyroscope.*"})` shows 3 Alloy targets, 1 Grafana and 1 Pyroscope;
  - `sum by (pod) (loki_write_sent_entries_total)` returns one row per `alloy-logs` pod and `alloy-singleton`;
  - `AlloyRemoteWriteSamplesFailed`, `PodLogsNotShipped`, and `PyroscopeQueryErrors` stay inactive on a healthy cluster;
  - `kubectl get ds -n logging` lists no `loki-canary`, `kubectl get clusterrole grafana-clusterrole` returns NotFound, and `kubectl get role -n monitoring grafana -o jsonpath='{.rules}'` grants `configmaps`;
  - `kubectl get sts -n monitoring pyroscope-alloy` returns NotFound, `kubectl get ds -n monitoring k8s-monitoring-alloy-profiles` is ready on every node, `kubectl get podlogs.monitoring.grafana.com -A` prints "No resources found" before `kubectl delete crd podlogs.monitoring.grafana.com`, and any zero-length `block.bin` torn segments in Pyroscope's `segments/` directory are backed up and moved aside with Pyroscope scaled to 0.

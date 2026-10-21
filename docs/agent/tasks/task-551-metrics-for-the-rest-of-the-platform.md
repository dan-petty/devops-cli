# Task: Metrics for the Rest of the Platform (#551)

**Issue**: [#551](https://github.com/dan-petty/devops-cli/issues/551)
**Scope**: scope/k8s, scope/telemetry
**Feasibility**: Confirmed against `k8s/argocd/values.yaml` (`argo/argo-cd` ServiceMonitors for `controller` 8082, `server` 8083, `repoServer` 8084, and `redis` exporter 9121), `k8s/llm/valkey.yaml` (`oliver006/redis_exporter:v1.67.0-alpine` sidecar on port 9121), `k8s/registry/deployment.yaml` (Distribution `REGISTRY_HTTP_DEBUG_ADDR` / `REGISTRY_HTTP_DEBUG_PROMETHEUS_ENABLED` on port 5001), `k8s/monitoring/networkpolicy.yaml`, and `k8s/monitoring/prometheus-values.yaml`.

## Description
Following the monitoring cleanup amendment (`#1128`), `#551` covers metrics collection, monitoring egress, and alerting for Argo CD, Valkey, the container registry, and Cloudflare Tunnel health:

- **Scrapes (one owner each via `k8s-monitoring` features)**:
  - **Argo CD (`k8s/argocd/values.yaml`)**: Enables chart `ServiceMonitor`s (`prometheusOperatorObjects`) for `controller` (port 8082), `server` (port 8083), `repoServer` (port 8084), and `redis` (with `redis.exporter.enabled: true` on port 9121). `k8s/argocd/networkpolicy.yaml` admits `monitoring` ingress on TCP `8082`, `8083`, `8084`, and `9121`.
  - **Valkey (`k8s/llm/valkey.yaml` and `k8s/llm/service.yaml`)**: Adds an `oliver006/redis_exporter:v1.67.0-alpine` sidecar container (`port: 9121`) and pod annotations (`prometheus.io/scrape: "true"`, `prometheus.io/port: "9121"`, `k8s.grafana.com/metrics.container: "redis-exporter"`) scraped by Alloy `annotationAutodiscovery`.
  - **Container Registry (`k8s/registry/deployment.yaml` and `k8s/registry/service.yaml`)**: Enables Distribution's built-in Prometheus endpoint on port `5001` (`REGISTRY_HTTP_DEBUG_ADDR: ":5001"`, `REGISTRY_HTTP_DEBUG_PROMETHEUS_ENABLED: "true"`) and pod annotations (`prometheus.io/scrape: "true"`, `prometheus.io/port: "5001"`) scraped by Alloy `annotationAutodiscovery`.
- **NetworkPolicies (`k8s/monitoring/networkpolicy.yaml` and `k8s/llm/networkpolicy.yaml`)**:
  - `k8s/monitoring/networkpolicy.yaml` admits egress to `argocd` on TCP `8082`, `8083`, `8084`, `9121`, `llm` on TCP `9121`, and `registry` on TCP `5001`.
  - `k8s/llm/networkpolicy.yaml` admits ingress from `monitoring` (`alloy-metrics`) on TCP `9121`.
- **Alerting (`k8s/monitoring/prometheus-values.yaml`, group `homelab-services`)**:
  - `ArgoCdApplicationOutOfSync` (`argocd_app_info{sync_status!="Synced"} == 1`, `for: 15m`, `warning`).
  - `ArgoCdApplicationUnhealthy` (`argocd_app_info{health_status!~"Healthy|Progressing"} == 1`, `for: 15m`, `warning`).
  - `ArgoCdAutoSyncDisabled` (`argocd_app_info{autosync_enabled="false"} == 1`, `for: 15m`, `warning`).
  - `ArgoCdSyncOperationStuck` (`argocd_app_info{operation!=""} == 1`, `for: 1h`, `warning`).
  - `CloudflareTunnelDegraded` (`sum(cloudflared_tunnel_ha_connections) < 2`, `for: 5m`, `warning`).
  - `ValkeyCacheErrors` (`redis_up == 0 or increase(redis_rejected_connections_total[5m]) > 0`, `for: 5m`, `warning`).

## Acceptance Criteria
- [x] New scrapes use `k8s-monitoring` features (`annotationAutodiscovery` for `valkey` and `registry`, and chart `ServiceMonitor`s through `prometheusOperatorObjects` for `argocd`), not server-side scrape jobs (`tests/test_k8s_monitoring_integration.py`).
- [x] Each new target has exactly one scrape owner (`test_each_annotated_component_has_one_scrape_owner`), and each new scrape port has exactly one monitoring egress rule (`test_every_scrape_port_has_one_egress_rule`).
- [x] `homelab-services` alerts cover Argo CD sync/health/autosync/stuck operations, Cloudflare Tunnel HA connectivity, and Valkey cache errors (`tests/test_k8s_monitoring_alerting.py`).
- Pending a person: after the next deploy, the `homelab-services` alerts' expressions return series, for example `argocd_app_info` and `redis_up`.

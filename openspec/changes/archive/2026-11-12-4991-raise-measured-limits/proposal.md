# Proposal

## Why

#4991: on 2026-11-12 the owner said that the cluster limits look unnecessarily low. 7 days of Prometheus data show that some memory limits are near the peak use, and that some CPU limits throttle containers that use only a few millicores. Today each limit is fixed only after a kill (#4116, #4149, #2806, #1815, #2391, #4939). This item is rank 1 of the cluster integration plan #4989.

## What Changes

- `k8s/monitoring/grafana-values.yaml`: the Grafana memory request goes from 256Mi to 512Mi, and the memory limit from 1024Mi to 2Gi.
- `k8s/llm/gateway/deployment.yaml`: the memory limit of container `litellm` goes from 2048Mi to 4Gi. A comment says why, and says not to set `MAX_REQUESTS_BEFORE_RESTART`.
- `k8s/monitoring/k8s-monitoring-values.yaml`: the memory limit of `alloy-metrics` goes from 1024Mi to 1536Mi, of `alloy-logs` from 512Mi to 768Mi, and the CPU limit of node-exporter from 200m to 500m.
- `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml` and `k8s/argocd/values.yaml`: the CPU limit of the redis_exporter sidecars goes from 100m to 500m.
- `k8s/devops/roadmap-service/deployment.yaml`: the CPU limit of container `service` goes from 1 to 2.
- Each changed `resources` block gets a comment with the measured value and #4991. The requests stay, except the Grafana memory request.
- Tempo stays at 2Gi (7 d peak 76%). The near-limit rule of #4993 watches it.
- Tests: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py` and `tests/server/routes/test_k8s_roadmap_service.py` hold the new values.
- The change carries spec deltas, because a manifest is observable: the new capability `workload-resource-limits` holds the memory limits and the exporter CPU limits, and `roadmap-service-deployment` changes the CPU limit of its requirement "The Service container has memory for the observed growth".
- The change fits one pull request.
- Rollout: Argo CD syncs the manifests from `main`. Each changed pod restarts once. No ConfigMap key changes. Nobody changes the cluster by hand.

## Capabilities

### New Capabilities

- `workload-resource-limits`: The memory limits have room above the measured peak; the exporter CPU limits do not throttle a scrape

### Modified Capabilities

- `roadmap-service-deployment`: The Service container has memory for the observed growth

## Impact

- Manifests: `k8s/monitoring/grafana-values.yaml`, `k8s/llm/gateway/deployment.yaml`, `k8s/monitoring/k8s-monitoring-values.yaml`, `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, `k8s/argocd/values.yaml`, `k8s/devops/roadmap-service/deployment.yaml`
- Tests: `tests/commands/k8s/test_k8s.py`, `tests/ai/benchmark/test_k8s_llm_gateway.py`, `tests/server/routes/test_k8s_roadmap_service.py`
- Scheduling: only the Grafana memory request grows (by 256Mi). Limits are not reserved on a node. Each node had 21 GiB or more of allocatable memory that no running pod requests.

## Feasibility

- The values were read again from Prometheus on 2026-11-12, through the Grafana datasource, with no write to the cluster.
- `max_over_time(container_memory_working_set_bytes[7d])` against `kube_pod_container_resource_limits`: Grafana 1014 MiB of 1024 MiB (99%), `litellm` 1333 MiB of 2048 MiB (65%), `alloy-metrics` 737 MiB of 1024 MiB (72%), `alloy-logs` 342 MiB of 512 MiB (67%).
- `increase(container_cpu_cfs_throttled_periods_total[7d]) / increase(container_cpu_cfs_periods_total[7d])`: `redis-exporter` of `valkey` 69%, of `valkey-devops` 52%, the Argo CD exporter (`metrics` of `argocd-redis`) 57%, node-exporter 29%, `service` of `roadmap-service` 8%. The peak 1-minute CPU rate of the exporters is 2m to 21m and of node-exporter 33m.
- The 7 d median scrape takes 0.19 s to 0.46 s for the Valkey exporters, 0.25 s for the Argo CD exporter and up to 1.9 s for node-exporter, against 0.008 s for the Prometheus self scrape.
- `max_over_time(rate(container_cpu_usage_seconds_total{container="service"}[2m])[7d:1m])` is 1.00 core at a limit of 1.
- The live limits match git: `kube_pod_container_resource_limits` reads 1 GiB (Grafana), 2 GiB (`litellm`), 1 GiB (`alloy-metrics`), 512 MiB (`alloy-logs`), 0.1 CPU (each exporter), 0.2 CPU (node-exporter) and 1 CPU (`service`). Argo CD syncs `main` with self-heal, so a change in git is the only change that stays.
- The first run of the changed tests on the base fails for the right reason: `['100m', '100m'] != ['500m', '500m']`, `('768Mi', '3Gi', '100m', '1') != ('768Mi', '3Gi', '100m', '2')`, and the gateway tuple without `4Gi`.
- Documents that name the old values: `git grep` finds only `openspec/specs/roadmap-service-deployment/spec.md` (the CPU limit `1`), which the delta changes. `k8s/README.md` names the memory of the Service, not its CPU limit, and names no limit of the other containers.

## Existing Tool Considered

KRR (robusta-dev/krr, MIT) recommends requests and limits from Prometheus history. #4992 adopts it for every container after this item. This item changes only the limits that the 7 d data already shows are too low, so it does not wait for #4992. The Vertical Pod Autoscaler needs a new controller and changes requests in the cluster, but the homelab keeps every request in git (Argo CD with prune and self-heal). The change deletes no internal code.

## Dependencies

None. #4993 (workload alerts) and #4992 (KRR) come after this item.

# workload-resource-limits Specification

## Purpose
The resource limits of the long-running workloads in the cluster manifests: each limit has room above the peak use that Prometheus measured over 7 days, so the kernel does not kill a container for memory and CFS does not throttle a container that uses only a few millicores.

## Requirements

### Requirement: The memory limits have room above the measured peak
The manifests SHALL give Grafana (`k8s/monitoring/grafana-values.yaml`) a memory request of `512Mi` and a memory limit of `2Gi`, the container `litellm` of `deployment/llm-gateway` (`k8s/llm/gateway/deployment.yaml`) a memory limit of `4Gi`, and the collectors of `k8s/monitoring/k8s-monitoring-values.yaml` the memory limits `1536Mi` (`alloy-metrics`) and `768Mi` (`alloy-logs`). The other requests and limits of these containers SHALL stay.

#### Scenario: The monitoring manifests are read
- **WHEN** `k8s/monitoring/grafana-values.yaml` and `k8s/monitoring/k8s-monitoring-values.yaml` are read
- **THEN** Grafana requests `100m` of CPU and `512Mi` of memory and limits them to `500m` and `2Gi`, `alloy-metrics` limits its memory to `1536Mi`, and `alloy-logs` limits its memory to `768Mi`

#### Scenario: The gateway manifest is read
- **WHEN** `k8s/llm/gateway/deployment.yaml` is read
- **THEN** the first container of the Deployment requests `200m` of CPU and limits it to `1000m`, and limits its memory to `4Gi`

### Requirement: The exporter CPU limits do not throttle a scrape
The `redis-exporter` sidecars of the Deployments `valkey` and `valkey-devops` in `k8s/llm/`, the Valkey exporter of Argo CD (`redis.exporter` in `k8s/argocd/values.yaml`) and node-exporter (`telemetryServices.node-exporter` in `k8s/monitoring/k8s-monitoring-values.yaml`) SHALL have a CPU limit of `500m`. Their CPU requests SHALL stay.

#### Scenario: The exporter manifests are read
- **WHEN** `k8s/llm/valkey.yaml`, `k8s/llm/valkey-devops.yaml`, `k8s/argocd/values.yaml` and `k8s/monitoring/k8s-monitoring-values.yaml` are read
- **THEN** each of the four exporters has a CPU limit of `500m`

### Requirement: The 16 GiB Ollama tier limits its memory to its request
The container `ollama` of the DaemonSet `ollama-16gib` (`k8s/llm/profiles/ollama-profiles.yaml`) SHALL have a memory request of `8Gi` and a memory limit of `8Gi`. Its CPU request SHALL stay `3000m`, with no CPU limit.

#### Scenario: The profiles manifest is read
- **WHEN** `k8s/llm/profiles/ollama-profiles.yaml` is read
- **THEN** the container `ollama` of `ollama-16gib` requests `8Gi` of memory and limits its memory to `8Gi`

### Requirement: The Tempo query limits stay under the memory limit
The Tempo Helm values (`k8s/otel/tempo-values.yaml`) SHALL set `tempo.queryFrontend.search.max_bytes_per_trace` to `1000000`, `max_result_limit` to `50`, `max_duration` to `30s` and `target_bytes_per_second` to `25000000`, SHALL set `tempo.queryFrontend.max_outstanding_per_tenant` to `10` and `tempo.querier.max_concurrent_queries` to `4`, SHALL set `tempo.global_overrides.max_bytes_per_trace` to `1000000`, and SHALL keep the memory limit of the `tempo` container at `2048Mi`.

#### Scenario: The Tempo values hold each limit
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, and it fails when one of the seven limits or the `2048Mi` memory limit differs from the value that this requirement names.

#### Scenario: An edited limit fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.max_outstanding_per_tenant` to `50`
- **THEN** The row fails and names `k8s/otel/tempo-values.yaml` and the key that differs.

#### Scenario: The outstanding searches fit under half of the memory limit
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, because ten outstanding searches of fifty results of `1000000` bytes hold 500000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit.

#### Scenario: The concurrent trace reads are bounded
- **WHEN** I run `uv run devops ci --check --only k8s` on `k8s/otel/tempo-values.yaml`
- **THEN** The row passes, because `tempo.querier.max_concurrent_queries` is `4`, no more than the `10` outstanding queries per tenant, and `4` times `tempo.global_overrides.max_bytes_per_trace` of `1000000` is 4000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit; it fails when the querier admits more concurrent queries than the outstanding-query limit.

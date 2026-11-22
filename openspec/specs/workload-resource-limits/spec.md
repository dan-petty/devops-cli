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
The Tempo configuration that chart `tempo` renders from `k8s/otel/tempo-values.yaml` SHALL set `query_frontend.max_outstanding_per_tenant`, `query_frontend.search.max_result_limit`, `query_frontend.api_timeout`, `querier.max_concurrent_queries` and `overrides.defaults.global.max_bytes_per_trace`. The searches and the concurrent reads that these limits admit SHALL hold at most half of the memory limit of the rendered `tempo` container.

#### Scenario: The Tempo values hold each limit
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, and it fails when the rendered Tempo configuration does not set one of the five keys that this requirement names, or the rendered `tempo` container has no memory limit.

#### Scenario: An edited limit fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.max_outstanding_per_tenant` to `50`
- **THEN** The row fails, because 50 outstanding queries of 50 results of `1000000` bytes are more than half of the memory limit, and it names `query_frontend.max_outstanding_per_tenant`.

#### Scenario: The outstanding searches fit under half of the memory limit
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because 10 outstanding queries of 50 results of `1000000` bytes are 500000000 bytes, under the 1073741824 bytes of half of the `2048Mi` limit.

#### Scenario: The concurrent trace reads are bounded
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because `querier.max_concurrent_queries` is `4`, no more than the `10` outstanding queries, and 4 concurrent queries of `1000000` bytes are 4000000 bytes, under half of the `2048Mi` limit; it fails when the querier admits more concurrent queries than the outstanding-query limit.

#### Scenario: A limit that the chart does not render fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit puts the trace size limit under `tempo.global_overrides`, which the chart does not render
- **THEN** The row fails and names `overrides.defaults.global.max_bytes_per_trace` of the rendered Tempo configuration.

### Requirement: The rendered Tempo configuration parses with the Tempo image of the chart
The `k8s` row of `devops ci` SHALL render the chart source of the Argo CD Application `tempo` (`k8s/argocd/apps/tempo.yaml`) with `helm template`, and SHALL start the image of the rendered `tempo` container with the arguments of that container, `-config.verify=true`, no network and the rendered ConfigMaps at their mount paths. The row SHALL fail when Tempo exits with a status other than 0, and SHALL name the output of Tempo.

#### Scenario: The rendered configuration parses
- **WHEN** I run `uv run devops ci --check --only k8s`
- **THEN** The row passes, because the Tempo image of the chart parses the rendered `/conf/tempo.yaml` and exits 0.

#### Scenario: A key that the pinned Tempo does not have fails the row
- **WHEN** I run `uv run devops ci --check --only k8s` after an edit sets `tempo.queryFrontend.search.max_bytes_per_trace`
- **THEN** The row fails and shows `field max_bytes_per_trace not found in type frontend.SearchConfig`.

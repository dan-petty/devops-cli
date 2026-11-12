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

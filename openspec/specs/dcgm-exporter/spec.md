# dcgm-exporter Specification

## Purpose
The NVIDIA DCGM exporter DaemonSet that exports GPU metrics to the monitoring stack, including its scrape settings, security context, and resource allocations.

## Requirements

### Requirement: DCGM exporter resource requests and limits fit its footprint
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL configure container resource requests and limits that fit its measured footprint, with a memory request of 512Mi, a memory limit of 768Mi, a CPU request of 50m, and a CPU limit of 200m.

#### Scenario: Values define explicit resource requests and limits
- **WHEN** the `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` are loaded
- **THEN** `resources.requests.cpu` equals `50m`
- **AND** `resources.requests.memory` equals `512Mi`
- **AND** `resources.limits.cpu` equals `200m`
- **AND** `resources.limits.memory` equals `768Mi`

### Requirement: The DCGM exporter collects the counter list of its values and restarts when the list changes
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL hold the exporter's counter list as `customMetrics`, SHALL pass no `arguments`, and SHALL set the pod annotation `checksum/counters` to the SHA-256 of `customMetrics`. The list SHALL ask for every metric family that a dashboard reads, with the type that the exporter prints, and SHALL ask for `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` as gauges.

#### Scenario: The values hold the counter list and its checksum
- **WHEN** `uv run devops ci --check --only k8s` renders the environment tree, and after the deploy `curl -s http://localhost:9400/metrics` runs through `kubectl -n monitoring port-forward daemonset/dcgm-exporter 9400:9400`
- **THEN** the render passes; the metrics page holds each family that a dashboard reads, among them `DCGM_FI_DEV_ENFORCED_POWER_LIMIT`, `DCGM_EXP_CLOCK_EVENTS_COUNT`, `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY`, the last two as `gauge`; and `kubectl -n monitoring get daemonset dcgm-exporter -o jsonpath='{.spec.template.metadata.annotations.checksum/counters}'` equals the SHA-256 of `customMetrics`

#### Scenario: A counter list that drops a captured family is found
- **WHEN** a counter list omits a family that a dashboard reads
- **THEN** the panel that reads that family shows "No data" on the cluster, so a person sees the gap

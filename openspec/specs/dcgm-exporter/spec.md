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
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL hold the exporter's counter list as `customMetrics` and SHALL pass no `arguments`, so the exporter reads the list that the chart mounts at `/etc/dcgm-exporter/default-counters.csv`. The list SHALL ask for every metric family in `tests/fixtures/metrics/dcgm-exporter.yaml`, with the type that the capture printed. The values SHALL set the pod annotation `checksum/counters` to the SHA-256 of `customMetrics`.

#### Scenario: The values hold the counter list and its checksum
- **WHEN** the `dcgm-exporter` Helm values are loaded
- **THEN** `arguments` is absent or empty
- **AND** `customMetrics` names each family of `tests/fixtures/metrics/dcgm-exporter.yaml` with its captured type, among them `DCGM_FI_DEV_ENFORCED_POWER_LIMIT` and `DCGM_EXP_CLOCK_EVENTS_COUNT`
- **AND** `podAnnotations.checksum/counters` equals the SHA-256 of `customMetrics`

#### Scenario: A counter list that drops a captured family is found
- **WHEN** a counter list omits a captured family or gives it another type
- **THEN** the check names that family with the type the list gives it, or with none

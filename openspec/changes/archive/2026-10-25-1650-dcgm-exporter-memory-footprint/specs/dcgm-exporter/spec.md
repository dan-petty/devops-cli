# Spec Delta

## Purpose

The NVIDIA DCGM exporter DaemonSet that exports GPU metrics to the monitoring stack, including its scrape settings, security context, and resource allocations.

## ADDED Requirements

### Requirement: DCGM exporter resource requests and limits fit its footprint
The `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` SHALL configure container resource requests and limits that fit its measured footprint, with a memory request of 512Mi, a memory limit of 768Mi, a CPU request of 50m, and a CPU limit of 200m.

#### Scenario: Values define explicit resource requests and limits
- **WHEN** the `dcgm-exporter` Helm values in `k8s/monitoring/dcgm-exporter-values.yaml` are loaded
- **THEN** `resources.requests.cpu` equals `50m`
- **AND** `resources.requests.memory` equals `512Mi`
- **AND** `resources.limits.cpu` equals `200m`
- **AND** `resources.limits.memory` equals `768Mi`

# log-and-metric-retention Specification

## Purpose
Alert rule evaluating storage space for log and metric local-path volumes while pods move between nodes.

## Requirements

### Requirement: The disk alert evaluates while a pod moves between nodes
The Prometheus alert rules SHALL include `LogOrMetricVolumeDiskLow`, severity `warning`, which alerts when a local-path volume for Loki or Prometheus has under 10% free space. The rule SHALL place `kube_pod_info` on the left of `group_left (persistentvolumeclaim)` so that multiple node series during pod transitions evaluate without many-to-many matching errors.

#### Scenario: The rule selects series for log and metric storage
- **WHEN** a test reads `LogOrMetricVolumeDiskLow` in `k8s/monitoring/prometheus-values.yaml`
- **THEN** its expression selects `node_filesystem_avail_bytes` and `node_filesystem_size_bytes` on `mountpoint`, `kube_pod_info`, and `kube_pod_spec_volumes_persistentvolumeclaims_info` on `persistentvolumeclaim=~"storage-loki-0|prometheus-server"`
- **AND** it uses `group_left (persistentvolumeclaim)`, does not use `group_left (node)`, and waits `30m`

# monitoring-collectors Specification

## Purpose
The Alloy collectors that the k8s-monitoring chart runs in the monitoring stack: the data that each collector keeps across a pod restart, and the nodes where it runs.

## ADDED Requirements

### Requirement: The alloy-metrics write-ahead log is on a volume claim
The `alloy-metrics` collector SHALL keep its write-ahead log on a volume from a claim template of its StatefulSet. `alloy.storagePath` SHALL be under a writable mount of that claim, so that a pod restart keeps the samples that Alloy buffered and did not send.

#### Scenario: The storage path is on the claim's mount
- **WHEN** the `alloy-metrics` collector values in `k8s/monitoring/k8s-monitoring-values.yaml` are read
- **THEN** `alloy.storagePath` is under the writable `alloy.mounts.extra` entry `alloy-wal`
- **AND** `controller.volumeClaimTemplates` holds the claim `alloy-wal` with the class `local-path`, the access mode `ReadWriteOnce` and a request of 1Gi

### Requirement: The alloy-metrics pod does not run on the control-plane node
The `alloy-metrics` pod SHALL have a required node affinity with the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`, so that local-path binds its volume on a node without the control-plane label.

#### Scenario: The affinity excludes the control-plane label
- **WHEN** the `alloy-metrics` collector values are read
- **THEN** `controller.affinity` holds one required node selector term with the one expression `node-role.kubernetes.io/control-plane` `DoesNotExist`

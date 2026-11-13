# monitoring-collectors Specification

## Purpose
The Alloy collectors that the k8s-monitoring chart runs in the monitoring stack: the data that each collector keeps across a pod restart, and the nodes where it runs.

## Requirements

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

### Requirement: The alloy-profiles pod does not run on the node hawk
The `alloy-profiles` collector values in `k8s/monitoring/k8s-monitoring-values.yaml` SHALL hold no `controller.affinity`, so its eBPF profiler runs on every node. The `alloy-logs` and `alloy-singleton` collectors SHALL hold no `controller.affinity`, and `alloy-metrics` SHALL keep its one required node selector term with the expression `node-role.kubernetes.io/control-plane` `DoesNotExist`.

#### Scenario: The affinity excludes the node
- **WHEN** A test reads the `collectors` block of `k8s/monitoring/k8s-monitoring-values.yaml`
- **THEN** The alloy-profiles, alloy-logs and alloy-singleton collectors hold no node affinity, and the alloy-metrics collector holds its one term with the control-plane label DoesNotExist

### Requirement: The OpenTelemetry collector sends metrics to the Prometheus OTLP receiver
The metrics pipeline of `k8s/otel/values.yaml` SHALL send only to an `otlp_http` exporter at the path `/api/v1/otlp/v1/metrics` of the Prometheus server, and SHALL set the datapoint attribute `cluster`. The Prometheus server SHALL run its OTLP receiver with `created-timestamp-zero-ingestion` and the translation strategy `UnderscoreEscapingWithoutSuffixes`, so that each new stream starts with a zero sample.

#### Scenario: The collector values are read
- **WHEN** a test reads the metrics pipeline of `k8s/otel/values.yaml`
- **THEN** it has one exporter, of type `otlp_http`, whose `metrics_endpoint` is port 9090 of `prometheus-server.monitoring.svc.cluster.local` with the path `/api/v1/otlp/v1/metrics`
- **AND** its one datapoint transform statement sets the datapoint attribute `cluster` to the cluster name of `k8s/monitoring/k8s-monitoring-values.yaml`

#### Scenario: The Prometheus server values are read
- **WHEN** a test reads `server` in `k8s/monitoring/prometheus-values.yaml`
- **THEN** `extraArgs` holds `web.enable-otlp-receiver`, `web.enable-remote-write-receiver` and `enable-feature: created-timestamp-zero-ingestion`
- **AND** `otlp` is `translation_strategy: UnderscoreEscapingWithoutSuffixes`

### Requirement: A stream with no delta for an hour starts again from zero
The `deltatocumulative` processor of the collector SHALL set `max_stale` to `1h`, because the roadmap-service rules read a series with no sample in the hour before as a new stream and count all of its last value.

#### Scenario: The collector values and the rules are read
- **WHEN** a test reads `k8s/otel/values.yaml` and `k8s/monitoring/prometheus-values.yaml`
- **THEN** `max_stale` of `deltatocumulative` is `1h`
- **AND** the rules hold a selector with `[1h] offset 1h`

## ADDED Requirements

### Requirement: The OpenTelemetry collector sends metrics to the Prometheus OTLP receiver
The metrics pipeline of `k8s/otel/values.yaml` SHALL send only to an `otlp_http` exporter at the path `/api/v1/otlp/v1/metrics` of the Prometheus server, and SHALL set the datapoint attribute `cluster`. The Prometheus server SHALL run its OTLP receiver with `created-timestamp-zero-ingestion` and the translation strategy `UnderscoreEscapingWithoutSuffixes`, so that each new stream starts with a zero sample.

#### Scenario: The collector values are read
- **WHEN** a test reads the metrics pipeline of `k8s/otel/values.yaml`
- **THEN** it has one exporter, of type `otlp_http`, whose `metrics_endpoint` is port 9090 of `prometheus-server.monitoring.svc.cluster.local` with the path `/api/v1/otlp/v1/metrics`
- **AND** its one transform statement sets the datapoint attribute `cluster` to the cluster name of `k8s/monitoring/k8s-monitoring-values.yaml`

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

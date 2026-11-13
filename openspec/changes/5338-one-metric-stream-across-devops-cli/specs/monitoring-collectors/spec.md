## MODIFIED Requirements

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

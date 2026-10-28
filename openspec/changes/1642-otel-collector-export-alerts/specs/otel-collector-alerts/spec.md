## Purpose

The alerts on the export health of the OpenTelemetry collector: a send to Tempo, Prometheus or Loki that keeps failing, and an exporter queue that stays almost full.

## ADDED Requirements

### Requirement: A failing export of the collector alerts
The Prometheus server SHALL fire `OtelCollectorExportFailing` with the severity `warning` for each exporter of the OpenTelemetry collector whose count of failed spans, metric points or log records increased in each 15-minute window for 15 minutes. The alert SHALL name the exporter and the signal (`traces`, `metrics` or `logs`) in its labels, and SHALL have no `node` label.

#### Scenario: An exporter keeps failing
- **WHEN** the `otel-collector` group is evaluated over a series of failed spans of `otlp_grpc/tempo`, failed metric points of `prometheus_remote_write` and failed log records of `otlp_http/loki`, each growing by 10 each minute
- **THEN** at 10 minutes no alert fires
- **AND** at 20 minutes `OtelCollectorExportFailing` fires once for each exporter, with `data_type` `traces`, `metrics` and `logs`

#### Scenario: One failed send
- **WHEN** a failed-spans counter grows once, at minute 5
- **THEN** `OtelCollectorExportFailing` does not fire at 18 minutes or at 25 minutes

#### Scenario: An exporter that sends again
- **WHEN** a failed-spans counter keeps the same value
- **THEN** `OtelCollectorExportFailing` does not fire for its exporter

### Requirement: An almost full exporter queue alerts
The Prometheus server SHALL fire `OtelCollectorExportQueueFull` with the severity `warning` for each exporter queue of the OpenTelemetry collector whose size stays at 90% or more of its capacity for 15 minutes. The alert SHALL name the exporter and the `data_type` of the queue, and SHALL have no `node` label.

#### Scenario: A queue at 95% and a queue at 50%
- **WHEN** the traces queue of `otlp_grpc/tempo` holds 950 of 1000 and the logs queue of `otlp_http/loki` holds 500 of 1000
- **THEN** at 10 minutes no alert fires
- **AND** at 20 minutes `OtelCollectorExportQueueFull` fires only for `otlp_grpc/tempo`, with the summary "The otlp_grpc/tempo queue of the OpenTelemetry collector is 95% full"

### Requirement: The collector rules read only the series the collector serves
Each series that an `otel-collector` rule selects SHALL be a family of the collector capture in `tests/fixtures/metrics/otel-collector.yaml`: a family that the collector printed, or one in `from_source` that it prints from its first event.

#### Scenario: The rules and the capture
- **WHEN** the selectors of the `otel-collector` rules are read
- **THEN** they name five series, and each one is a family of the capture

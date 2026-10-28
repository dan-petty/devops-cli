# otlp-export Specification

## Purpose
How devops-cli sends OpenTelemetry data to the collector: over OTLP/HTTP through the egress-checked client, how an export that fails is reported, how the collector is probed, and how a gRPC setting is refused.

## Requirements

### Requirement: Each signal is posted to its OTLP/HTTP path
The real exporter SHALL post each export request to the path of its signal on the configured endpoint, `/v1/traces`, `/v1/metrics` or `/v1/logs`, through the egress-checked HTTP client at the private level.

#### Scenario: A request of each signal
- **WHEN** the exporter sends a trace, a metric and a log export request to a collector on a loopback port
- **THEN** the collector receives each request on the path of its signal, with the body that was sent

### Requirement: An export that the collector does not take counts a failure with a fixed text
A 2xx answer SHALL count one success. Any other answer SHALL count one failure and record `HTTP <status>` in `last_export_error`. A failed connection SHALL count one failure and record "Cannot connect to the collector".

#### Scenario: A collector that answers 503
- **WHEN** a telemetry client exports a span to a collector that answers 503
- **THEN** the client counts no success and one failure, and its `last_export_error` is `HTTP 503`

#### Scenario: A collector that does not run
- **WHEN** a telemetry client exports a span to a loopback port that refuses each connection
- **THEN** the client counts one failure, and its `last_export_error` is "Cannot connect to the collector"

### Requirement: The probe sends an empty export request
The collector probe SHALL post an export request that holds no spans to `/v1/traces`. A 2xx answer SHALL report the collector as reachable with `HTTP <status> OK`. Another answer SHALL report it as unreachable with `HTTP <status> probe failed`, and a failed connection with "Connection probe failed".

#### Scenario: A reachable and an unreachable collector
- **WHEN** the probe reaches a collector that answers 200, and then a port that refuses each connection
- **THEN** it reports `HTTP 200 OK` as reachable, and then "Connection probe failed" as unreachable

### Requirement: A gRPC setting is refused with its name
Building the exporter SHALL fail with an error that names `OTEL_EXPORTER_OTLP_PROTOCOL` when that variable holds a value other than `http/json` or `http/protobuf`. With no protocol, it SHALL fail with an error that names `telemetry.endpoint` when the endpoint has the `grpc` scheme or port 4317.

#### Scenario: The protocol variable asks for gRPC
- **WHEN** `OTEL_EXPORTER_OTLP_PROTOCOL` is `grpc`
- **THEN** building the exporter fails with an error that names `OTEL_EXPORTER_OTLP_PROTOCOL`

#### Scenario: The endpoint names the gRPC port
- **WHEN** no protocol is set and the endpoint is `http://collector.example.com:4317`
- **THEN** building the exporter fails with an error that names `telemetry.endpoint`

### Requirement: A refused setting keeps the command running with export off
When the configured protocol or endpoint is refused, the process tracer SHALL have export off, SHALL log one warning that starts with "Telemetry export is off:", and its probe SHALL report the refusal.

#### Scenario: A command with a gRPC protocol
- **WHEN** telemetry is on and `OTEL_EXPORTER_OTLP_PROTOCOL` is `grpc`
- **THEN** the process tracer has export off, one warning is logged, and its probe reports the message that names `OTEL_EXPORTER_OTLP_PROTOCOL`

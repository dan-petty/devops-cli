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

### Requirement: The devops perimeter opens only OTLP/HTTP to the collector
The NetworkPolicy of the `devops` namespace SHALL allow egress to the `otel` namespace on TCP 4318 only, and not on the OTLP gRPC port, 4317.

#### Scenario: The devops egress rule to otel
- **WHEN** a person runs `kubectl -n devops get networkpolicy -o yaml` on the cluster
- **THEN** the egress rule whose peer is the `otel` namespace names the one port TCP 4318

### Requirement: The export queue is bounded
The tracer SHALL keep at most `DEFAULT_OTEL_EXPORT_QUEUE_MAX_PAYLOADS` payloads that wait for export or are in export, and SHALL count each payload that it drops in `export_dropped`.

#### Scenario: A collector that does not answer
- **WHEN** the exporter blocks and the tracer sends 1000 payloads, with the cap at 16
- **THEN** the collector takes 16 payloads once it answers, and `export_dropped` is 984.

### Requirement: A process that runs on exports its metrics at a fixed interval
The tracer SHALL export the metrics that it holds every `OTEL_METRIC_EXPORT_INTERVAL` milliseconds from the first metric of the process on, through the same flush as the end of a command. The interval SHALL be 60000 milliseconds when the variable is not set, or when its value is not a finite number of milliseconds above zero. Each export SHALL hold only the deltas since the export before it.

#### Scenario: A long command exports before it ends
- **WHEN** a command records tokens and runs on past the interval
- **THEN** the collector holds the tokens while the command still runs

#### Scenario: A periodic export and a round flush count each delta once
- **WHEN** the process records 3 tokens, exports at the interval, records 2 tokens and flushes after a round
- **THEN** the exported deltas add up to 5, and each point starts at or after the end of the point before it

#### Scenario: A short command exports once
- **WHEN** a command records tokens and ends before the first interval
- **THEN** the collector gets one metric export request, and no export thread runs after the shutdown

#### Scenario: A value that is not a number of milliseconds above zero
- **WHEN** `OTEL_METRIC_EXPORT_INTERVAL` is zero, negative, infinite or not a number
- **THEN** the interval is 60 seconds

### Requirement: SIGTERM exports the telemetry before the process stops
The `devops` entry point SHALL set a SIGTERM handler that exports what the tracer holds and then does what the handler before it did. The handler SHALL call a Python handler before it, keep an ignored signal ignored, and else set the default action and send SIGTERM to the process again.

#### Scenario: A Python handler before
- **WHEN** a process with a Python SIGTERM handler runs the `devops` entry point, records tokens and gets SIGTERM
- **THEN** the collector holds the tokens, and the handler before runs once

#### Scenario: The default action before
- **WHEN** a process with the default action for SIGTERM installs the handler, records tokens and gets SIGTERM
- **THEN** the process exports one metric request, and SIGTERM ends it

#### Scenario: Two installs keep one handler
- **WHEN** the handler is installed two times and uninstalled one time
- **THEN** the handler before the first install is in place

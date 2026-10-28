# Design

## Context

The tracer builds OTLP/JSON export requests and queues them on its own executor. Tests need to read what it exports without patching it, #2437 needs the telemetry clients on the egress-checked factory, and a gRPC setting silently lost every export.

## Decisions

### The seam is the collector edge, not the SDK exporter interface

`OtlpExporter` takes one signal's encoded request (`signal`, `body`, `content_type`) and answers a probe. The tracer keeps its executor, its dry-run suppression and its counters.

- Rejected: the SDK's `SpanExporter` and `MetricExporter` as the seam, which the 2026-10-08 amendment proposed. A `SpanExporter` takes SDK `ReadableSpan` objects, and the tracer's spans are hand-built dicts until #2536 moves them onto the SDK. The SDK exporters of #2536 encode with the official encoders and call this seam, so the egress-checked client, the fake and the contract suite stay.
- Rejected: a Protocol around today's payload dicts. The seam takes bytes and a content type, so the protobuf of #2536 changes no signature.

### The fake records what the collector receives

`FakeCollector` implements `OtlpExporter`. It records each request decoded, gives the spans, metric data points and log records as plain values, and answers with the real exporter's failure texts.

- Rejected: `InMemorySpanExporter` and `InMemoryMetricReader` as the fake. The spans and logs are not SDK objects, and neither double answers with a failure or a probe result, which the contract suite compares.
- Rejected: #1314's HTTP fake. #1314 is not built, and the owner sequenced it after #2430, #2431 and #2437.

### Every failure has one text on both sides

`HttpOtlpExporter` turns a non-2xx answer into `HTTP <status>`, a failed connect into "Cannot connect to the collector" and a timeout into "The collector did not answer in time". The tracer records the text in `last_export_error`, and the daily warning shows it. Before, a refused connect recorded the operating system's text, which a fake cannot give.

### The probe sends an empty request

The probe posts `{"resourceSpans":[]}` to `/v1/traces`, which is valid OTLP: the collector answers it and stores nothing. Before, each probe stored a `ping` span of the service `devops-cli-ping`. A 2xx answer is reachable.

### gRPC fails with the setting's name

`otlp_exporter` raises `OtlpProtocolError` for a protocol other than `http/json` or `http/protobuf`, or, with no protocol, for an endpoint with the `grpc` scheme or port 4317. An explicit `http/*` protocol wins over the port. `get_tracer()` catches it: the command runs, export is off, the warning names the setting, and the probe of `devops telemetry status` reports the message. A command that builds a client for an endpoint it was given, such as `devops telemetry connect`, gets the error.

- Rejected: a gRPC exporter. The OTLP collector of the cluster serves OTLP/HTTP on 4318, and the gRPC exporter would bypass the egress-checked client.

### The fixture installs an exporter, not a tracer

`install_exporter` makes every tracer that `get_tracer()` builds export to the exporter with export on, until `remove_exporter`. The `config` fixture resets the tracer when a test changes settings, so an installed tracer would be dropped in the middle of a test, and the export would go to the configured, disabled tracer.

- Rejected: patching `get_tracer`, as the `captured` fixture did. It reached only the callers that read `tracer_module.get_tracer`.
- The floor's reset list calls `remove_exporter` after each test, so an exporter that a test installs and does not remove leaves with the test.

### `opentelemetry-sdk` becomes a direct dependency

`src` imports `opentelemetry.sdk.metrics` for the `MeterProvider`. With `opentelemetry-exporter-otlp-proto-grpc` gone, the SDK arrives only through `logfire`, so it is declared at the locked version, 1.45.1.

## ADDED Requirements

### Requirement: Service JSON log lines carry the ids of the open span
Each JSON line that the roadmap Service writes to stdout while a span is open SHALL carry the `trace_id` and `span_id` of that span: a span of the own tracer, else the current OpenTelemetry span. A line written with no open span SHALL carry neither key.

#### Scenario: A line written in a span of the own tracer
- **WHEN** a Service logger writes a record while a span of the own tracer is open
- **THEN** the JSON line carries the `trace_id` and `span_id` of the exported span

#### Scenario: A line written in an OpenTelemetry span
- **WHEN** a Service logger writes a record while only an OpenTelemetry SDK span is open
- **THEN** the JSON line carries that span's trace id as 32 hex characters and its span id as 16 hex characters

#### Scenario: A line written with no open span
- **WHEN** a Service logger writes a record with no open span
- **THEN** the JSON line has no `trace_id` key and no `span_id` key

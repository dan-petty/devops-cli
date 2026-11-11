# library-spans Specification

## Purpose
The spans that pydantic-ai, the MCP client and the LLM gateway client make through the OpenTelemetry API: how they nest under the own spans of devops-cli, what text they hold, how they reach the collector, and which host gets their trace context.

## Requirements

### Requirement: Agent spans nest under the span open at the run
While telemetry export is on, a pydantic-ai agent run SHALL export an `invoke_agent` span, a `chat` span for each model request with `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` and `gen_ai.usage.cache_read.input_tokens`, and an `execute_tool` span for each tool call. These spans SHALL be in the trace of the span open at the run and nest under it. An own span in a tool call SHALL nest under the `execute_tool` span.

#### Scenario: A stage agent with one tool call in a row span
- **WHEN** an agent that calls one tool runs in a `service.job` span
- **THEN** the collector gets one trace with `invoke_agent` under `service.job`, each `chat` span and the `execute_tool` span under `invoke_agent`, and the own span of the tool under `execute_tool`
- **AND** each `chat` span holds its input, output and cache read tokens

### Requirement: Library spans hold no prompt or tool text by default
While `telemetry.capture_llm_content` is false, which is the default, the pydantic-ai spans SHALL hold no text of a prompt, a reply, a tool argument or a tool result.

#### Scenario: An agent run with content capture off
- **WHEN** an agent runs with a prompt and a tool reply that each hold a marker phrase
- **THEN** no attribute of an exported span holds either marker phrase

### Requirement: Library spans go through the exporter of the tracer
Library spans SHALL go to the collector through the exporter of the process's tracer, as OTLP protobuf in batches. In a dry run, no library span SHALL be sent. The process SHALL set no `OTEL_EXPORTER_OTLP_ENDPOINT` and use no stock OTLP exporter for them.

#### Scenario: An agent run in a dry run
- **WHEN** an agent runs in a row span during a dry run
- **THEN** the collector gets no export request

#### Scenario: A protobuf trace request
- **WHEN** the exporter sends a protobuf trace request
- **THEN** the collector gets the span it encodes, on the path of the trace signal

### Requirement: Trace context goes to the gateway only
The requests of the LLM gateway client SHALL carry the `traceparent` of their HTTP client span. The global propagator of the OpenTelemetry API SHALL inject nothing, so no other request, an MCP request included, SHALL get a `traceparent` or `baggage` from the library span instrumentation.

#### Scenario: A gateway call and a call to another host
- **WHEN** an agent calls the gateway and then the same span sends a request to another host
- **THEN** the gateway request carries the `traceparent` of its `POST` span, and the other request carries none

#### Scenario: An MCP tool call in a row span
- **WHEN** an agent calls a tool of a roadmap MCP server in a row span that holds baggage
- **THEN** the `_meta` of the tool request holds no `traceparent`, `tracestate` or `baggage`

### Requirement: The Logfire bridge exports through the exporter of the tracer
When the `--logfire` option of a review command turns on the Logfire bridge, Logfire SHALL own the agent spans, and the bridge SHALL hand its spans to the collector through the exporter of the tracer. The bridge SHALL send nothing to Logfire's cloud and pass no token. While an `OTEL_EXPORTER_OTLP_*ENDPOINT` variable is set, the bridge SHALL NOT configure Logfire, because Logfire then adds a stock OTLP exporter.

#### Scenario: A span of the Logfire bridge
- **WHEN** the Logfire bridge is on and an agent span ends under a row span
- **THEN** the collector gets the agent span under the row span
- **AND** the library span setup sets no provider of its own

#### Scenario: A Logfire token is set
- **WHEN** `LOGFIRE_TOKEN` is set and the bridge starts
- **THEN** the bridge configures Logfire with `send_to_logfire=False` and no token

#### Scenario: An OTLP endpoint variable is set
- **WHEN** `OTEL_EXPORTER_OTLP_ENDPOINT` or a signal endpoint variable is set and the bridge starts
- **THEN** the bridge stops with `LogfireConfigurationError`, which names the variable, and does not configure Logfire

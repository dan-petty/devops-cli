## ADDED Requirements

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
The requests of the LLM gateway client SHALL carry the `traceparent` of their HTTP client span. The library span instrumentation SHALL put no `traceparent` on a request of another client.

#### Scenario: A gateway call and a call to another host
- **WHEN** an agent calls the gateway and then the same span sends a request to another host
- **THEN** the gateway request carries the `traceparent` of its `POST` span, and the other request carries none

### Requirement: Agent spans reach the collector with the Logfire bridge on
When `devops review --logfire` configures the Logfire bridge, the agent spans SHALL also go to the collector through the exporter of the tracer.

#### Scenario: An agent run with the Logfire bridge on
- **WHEN** the Logfire bridge is on and an agent runs in a row span
- **THEN** the collector gets the `invoke_agent` span under the row span

# llm-telemetry-content Specification

## Purpose
Control the recording of LLM prompt and response content in OpenTelemetry and Logfire spans, and scrub private host patterns from telemetry.

## Requirements

### Requirement: Model prompt and reply text kept out of telemetry by default
While `telemetry.capture_llm_content` is false, which is the default, native AI inference spans SHALL NOT include `llm.prompt_preview` or `llm.response_preview`. Logfire bridge instrumentation SHALL configure `instrument_pydantic_ai(include_content=False)` and scrub private host patterns using `PRIVATE_HOST_PATTERNS`.

#### Scenario: Inference span with capture disabled
- **WHEN** devops-cli executes an LLM dispatch call while `telemetry.capture_llm_content` is false
- **THEN** the `ai.llm.dispatch` span contains no `llm.prompt_preview` attribute
- **AND** the `ai.llm.dispatch` span contains no `llm.response_preview` attribute

#### Scenario: Logfire scrubbing of private host in span attribute
- **WHEN** Logfire is configured with telemetry enabled
- **THEN** Logfire configuration receives `ScrubbingOptions` with `PRIVATE_HOST_PATTERNS`
- **AND** any span attribute containing an internal host such as `node1.example.internal` is scrubbed

### Requirement: Model prompt and reply text captured when enabled
While `telemetry.capture_llm_content` is true, native AI inference spans SHALL record `llm.prompt_preview` and `llm.response_preview`. Logfire bridge instrumentation SHALL configure `instrument_pydantic_ai(include_content=True)`.

#### Scenario: Inference span with capture enabled
- **WHEN** devops-cli executes an LLM dispatch call while `telemetry.capture_llm_content` is true
- **THEN** the `ai.llm.dispatch` span contains the `llm.prompt_preview` attribute
- **AND** the `ai.llm.dispatch` span contains the `llm.response_preview` attribute

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

### Requirement: The inference span names the deployment model that served a gateway call
The `ai.llm.dispatch` inference span SHALL record `gen_ai.response.model` as the deployment model that the gateway reply names, and, when the gateway names no deployment model, as the model the reply body names. `gen_ai.request.model` SHALL keep the model the client asked for.

#### Scenario: A gateway reply names its deployment model
- **WHEN** a `devops-chat` call through the gateway gets a reply that names `openai/gpt-4o` and whose body names `devops-chat`
- **THEN** the `ai.llm.dispatch` span records `gen_ai.response.model` `openai/gpt-4o`
- **AND** it records `gen_ai.request.model` `devops-chat`

#### Scenario: A reply names no deployment model
- **WHEN** a `devops-chat` call through the gateway gets a reply that names no deployment model and whose body names `qwen3.8:27b`
- **THEN** the `ai.llm.dispatch` span records `gen_ai.response.model` `qwen3.8:27b`
- **AND** it records `gen_ai.request.model` `devops-chat`

### Requirement: The gateway sends spans with no message content to the Collector only
The LLM gateway SHALL run the LiteLLM `otel` callback beside `prometheus`, with `turn_off_message_logging` on and LiteLLM metrics and events off. It SHALL send OTLP/HTTP to the Service of the Collector chart on port 4318. Its egress on that port SHALL admit only the Collector pods.

#### Scenario: The rendered gateway names the Collector Service
- **WHEN** the `k8s` row of `devops ci` renders `k8s/llm/gateway`
- **THEN** the callbacks are `otel` and `prometheus` and `turn_off_message_logging` is true
- **AND** `OTEL_EXPORTER_OTLP_ENDPOINT` names `<release>-<chart>.otel.svc.cluster.local:4318` of the Collector's Argo CD Application

#### Scenario: The gateway reaches no other pod on the OTLP port
- **WHEN** the `k8s` row reads the egress of `llm-gateway-perimeter`
- **THEN** one rule admits TCP 4318, to the Collector pods of namespace `otel` alone
- **AND** the Collector perimeter admits TCP 4318 from every namespace

### Requirement: The Collector deletes gateway key data before Tempo
The traces pipeline of the Collector SHALL run a `transform` processor after `memory_limiter` and before `batch`. It SHALL delete each `metadata.user_api_key_*` and `metadata.requester_custom_headers` span attribute, and each span or event attribute whose name holds `authorization` or `api-key`. It SHALL replace each 64-digit hex value in gateway span and event attributes.

#### Scenario: A gateway span loses its key data
- **WHEN** the `k8s` row applies the statements of the processor to a gateway span with the LiteLLM key attributes and a refused-key error event
- **THEN** no key attribute and no key hash stays on the span or the event
- **AND** the model, route, token and error class attributes stay

#### Scenario: A devops-cli span keeps its digests
- **WHEN** the `k8s` row applies the statements to a devops-cli span with a 64-digit hex digest
- **THEN** the span keeps every attribute and value

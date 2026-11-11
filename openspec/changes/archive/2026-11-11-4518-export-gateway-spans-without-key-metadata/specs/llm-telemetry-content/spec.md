## ADDED Requirements

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

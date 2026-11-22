## MODIFIED Requirements

### Requirement: The gateway sends spans with no message content to the Collector only
The LLM gateway SHALL run the LiteLLM `otel` callback beside `prometheus`, with `turn_off_message_logging` on and LiteLLM metrics and events off. It SHALL send OTLP/HTTP to the Service of the Collector chart on port 4318. Its egress on that port SHALL admit only the Collector pods.

#### Scenario: The rendered gateway names the Collector Service
- **WHEN** the `k8s` row of `devops ci` renders `k8s/llm/gateway`
- **THEN** the callbacks are `otel` and `prometheus` and `turn_off_message_logging` is true
- **AND** `OTEL_EXPORTER_OTLP_ENDPOINT` names `<release>-<chart>.otel.svc.cluster.local:4318` of the Collector's Argo CD Application

#### Scenario: The gateway reaches no other pod on the OTLP port
- **WHEN** the `k8s` row reads the egress of `llm-gateway-perimeter-egress`
- **THEN** one rule admits TCP 4318, to the Collector pods of namespace `otel` alone
- **AND** the Collector perimeter admits TCP 4318 from every namespace

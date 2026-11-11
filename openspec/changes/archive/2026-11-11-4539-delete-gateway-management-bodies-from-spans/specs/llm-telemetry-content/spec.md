## MODIFIED Requirements

### Requirement: The Collector deletes gateway key data before Tempo
The traces pipeline of the Collector SHALL run a `transform` processor after `memory_limiter` and before `batch`. It SHALL delete each `metadata.user_api_key_*` and `metadata.requester_custom_headers` span attribute, each span or event attribute whose name holds `authorization` or `api-key`, and each `request.*` and `response.*` attribute of gateway spans. It SHALL replace each 64-digit hex value in gateway span and event attributes.

#### Scenario: A gateway span loses its key data
- **WHEN** the `k8s` row applies the statements of the processor to a gateway span with the LiteLLM key attributes and a refused-key error event
- **THEN** no key attribute and no key hash stays on the span or the event
- **AND** the model, route, token and error class attributes stay

#### Scenario: A gateway management span loses its request and response bodies
- **WHEN** the `k8s` row applies the statements to a gateway span with a raw key in `request.key`, callback secrets in `request.callback_vars` and a team row in `response.data`
- **THEN** no `request.*` and no `response.*` attribute stays on the span

#### Scenario: A devops-cli span keeps its digests
- **WHEN** the `k8s` row applies the statements to a devops-cli span with a 64-digit hex digest
- **THEN** the span keeps every attribute and value

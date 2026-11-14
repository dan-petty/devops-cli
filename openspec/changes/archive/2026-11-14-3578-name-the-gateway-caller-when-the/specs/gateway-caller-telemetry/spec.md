## ADDED Requirements

### Requirement: An empty service name still names devops-cli
`gateway_caller_headers` SHALL return a non-empty value for `x-litellm-end-user-id` on every gateway request, and the value SHALL be `devops-cli` when the process's OTel service name is empty.

#### Scenario: An empty OTel service name
- **WHEN** `OTEL_SERVICE_NAME` is set to an empty string
- **THEN** a chat call, an embedding call and a pydantic-ai agent call each send `x-litellm-end-user-id: devops-cli`

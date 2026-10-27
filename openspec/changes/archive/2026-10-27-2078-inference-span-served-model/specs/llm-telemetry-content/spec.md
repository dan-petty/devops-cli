## ADDED Requirements

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

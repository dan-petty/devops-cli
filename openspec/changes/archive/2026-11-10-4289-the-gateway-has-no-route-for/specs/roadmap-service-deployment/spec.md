## MODIFIED Requirements

### Requirement: The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models
`k8s/llm/gateway/config.yaml` SHALL serve `typesafe/jev-1.14` as the authenticated pass-through `POST /v1/systemone` to the System One endpoint of OpenRouter, with the OpenRouter key from the environment of the gateway, and SHALL NOT list it in `model_list`. The path of `SystemOneModel` under `ai.gateway_url` SHALL be that path. `resolve_pydantic_ai_model` SHALL resolve `typesafe/jev-1.14` to `SystemOneModel` and `"auto"` to a `FallbackModel` of a `DecisionModel`.

#### Scenario: The gateway config and model bridge are inspected
- **WHEN** the model that the bridge builds for `typesafe/jev-1.14` posts one request, `k8s/llm/gateway/config.yaml` is loaded, and `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` and `auto`
- **THEN** the path of the request is the `path` of an entry of `general_settings.pass_through_endpoints` that targets the System One endpoint of OpenRouter with `auth: true`
- **AND** `model_list` holds no entry named `typesafe/jev-1.14`
- **AND** `resolve_pydantic_ai_model` returns a `SystemOneModel` for `typesafe/jev-1.14` and a `FallbackModel` wrapping `DecisionModel` for `auto`

#### Scenario: The client reads the answer of OpenRouter
- **WHEN** the answer holds `id`, `provider` and `usage.cost` next to `model`, `answers` and `usage`
- **THEN** the client returns the answers and the usage without an error

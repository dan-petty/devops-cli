## MODIFIED Requirements

### Requirement: The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models
`k8s/llm/gateway/config.yaml` SHALL serve `typesafe/jev-1.14` as the pass-through `POST /v1/systemone` to `https://openrouter.ai/api/v1/systemone`, with `auth: true`, `forward_headers: false`, `methods: [POST]` and the header `Authorization` taken from `os.environ/OPENROUTER_API_KEY`. `model_list` and `CONST_AI_GATEWAY_HOSTED_MODELS` SHALL NOT name `typesafe/jev-1.14`, because OpenRouter refuses a decision model on chat completions. The path that `SystemOneModel` posts to under `ai.gateway_url` SHALL be that pass-through path. `resolve_pydantic_ai_model` SHALL resolve `typesafe/jev-1.14` to `SystemOneModel` with `typesafe_model_profile` and `"auto"` to a `DecisionModel` backed by a `FallbackModel`.

#### Scenario: The gateway config and model bridge are inspected
- **WHEN** the model that the bridge builds for `typesafe/jev-1.14` posts one request, `k8s/llm/gateway/config.yaml` is loaded, and `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` and `auto`
- **THEN** the path of the request is the `path` of an entry of `general_settings.pass_through_endpoints` that targets the System One endpoint of OpenRouter with `auth: true`
- **AND** `model_list` holds no entry named `typesafe/jev-1.14`
- **AND** `resolve_pydantic_ai_model` returns a `SystemOneModel` for `typesafe/jev-1.14` and a `FallbackModel` wrapping `DecisionModel` for `auto`

#### Scenario: The client reads the answer of OpenRouter
- **WHEN** the answer holds `id`, `provider` and `usage.cost` next to `model`, `answers` and `usage`
- **THEN** the client returns the answers and the usage without an error

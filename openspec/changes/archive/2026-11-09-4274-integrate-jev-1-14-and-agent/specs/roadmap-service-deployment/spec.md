## ADDED Requirements

### Requirement: The LLM gateway serves typesafe/jev-1.14 and the bridge resolves System One and auto models
`k8s/llm/gateway/config.yaml` and `CONST_AI_GATEWAY_HOSTED_MODELS` SHALL include `typesafe/jev-1.14` (`openrouter/typesafe/jev-1.14`, `max_input_tokens: 262144`, `data_collection: deny`). `resolve_pydantic_ai_model` SHALL resolve `typesafe/jev-1.14` to `SystemOneModel` with `typesafe_model_profile` and `"auto"` to a `DecisionModel` backed by a `FallbackModel`.

#### Scenario: The gateway config and model bridge are inspected
- **WHEN** `k8s/llm/gateway/config.yaml` is loaded and `resolve_pydantic_ai_model` resolves `typesafe/jev-1.14` and `auto`
- **THEN** `typesafe/jev-1.14` is present in `model_list` and `CONST_AI_GATEWAY_HOSTED_MODELS`
- **AND** `resolve_pydantic_ai_model` returns a `SystemOneModel` for `typesafe/jev-1.14` and a `FallbackModel` wrapping `DecisionModel` for `auto`

### Requirement: The devops stack includes the role-scoped MCP server and disables workload telemetry banners
`k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]` SHALL include `k8s/devops/mcp-server/` (`deployment.yaml`, `service.yaml`, `networkpolicy.yaml`, `networkpolicy-client.yaml`), and `mcp-server`, `cronjob-runner`, and `roadmap-service` SHALL set `DO_NOT_TRACK=1`, `OPENSPEC_TELEMETRY=0`, `OPENSPEC_NO_UPDATE_CHECK=1`, and `PYDANTIC_AI_NO_BANNER=1`.

#### Scenario: The devops kustomization and workload manifests are read
- **WHEN** `k8s/devops/` manifests are validated
- **THEN** `mcp-server` is listed in `k8s/devops/kustomization.yaml` and `MANIFESTS_BY_STACK["devops"]`
- **AND** `mcp-server`, `cronjob-runner`, and `roadmap-service` set the four telemetry and banner opt-out variables

## ADDED Requirements

### Requirement: Live gateway status queries model info and marks static fallbacks not checked
When `GET /model/info` answers, `devops ai gateway status` SHALL authenticate with the configured AI API key (`get_ai_api_key`) and render each served group and deployment while preserving recorded failover routes in `gateway_state.json`. When `GET /model/info` does not answer, `devops ai gateway status` SHALL fall back to `DEFAULT_GATEWAY_ROUTES` and mark each fallback row as `not checked`.

#### Scenario: Live gateway answers model info with active failover
- **WHEN** `devops ai gateway status` runs with an AI API key configured, a recorded failover, and a gateway returning two `devops-chat` deployments and `qwen3-embedding:0.6b` from `GET /model/info`
- **THEN** `GET /model/info` carries the configured bearer key, both `devops-chat` deployments and `qwen3-embedding:0.6b` render (`checked: true`), and the failover record stays active

#### Scenario: Model info is unreachable
- **WHEN** `devops ai gateway status` runs and `GET /model/info` fails or times out
- **THEN** `DEFAULT_GATEWAY_ROUTES` render with `not checked` (`checked: false`)

### Requirement: Gateway virtual models and default routes match served config groups
Every `virtual_model` in `DEFAULT_GATEWAY_ROUTES` and every entry in `CONST_AI_GATEWAY_VIRTUAL_MODELS` (including `qwen3-embedding:0.6b` in place of the unserved alias) SHALL be a declared `model_name` in `k8s/llm/gateway/config.yaml`.

#### Scenario: Absent virtual model fails the drift check
- **WHEN** the gateway config drift helper evaluates a virtual model name absent from `k8s/llm/gateway/config.yaml`
- **THEN** it returns the absent name and fails the route check

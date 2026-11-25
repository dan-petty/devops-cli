## ADDED Requirements

### Requirement: Unprefixed and gateway Jev targets require a version digit
`is_jev_model_target` and `is_decision_model_name` in `src/devops_cli/config/settings.py` SHALL accept a Jev target only when a digit follows `jev-` (`^(?:typesafe/)?jev-\d`). `is_decision_model_name`, `_is_jev_decision_name`, and `_model_prefix_and_target` in `src/devops_cli/ai/pydantic_ai_bridge.py` SHALL use this rule so unversioned router names do not pass validation or resolve to `SystemOneModel`.

#### Scenario: Unprefixed and prefixed router targets are refused while versioned targets pass
- **WHEN** a test calls `is_jev_model_target` and `is_decision_model_name` with `typesafe/jev-router` and `jev-router`, calls `is_decision_model_name` with `openai-chat:jev-router`, and calls both helpers with `typesafe/jev-1.14` and `jev-1.13`
- **THEN** all router calls return `False` and all versioned calls return `True`

#### Scenario: Settings loader refuses router decision model
- **WHEN** `load_settings()` loads a config with `ai.decision_model: typesafe/jev-router`
- **THEN** validation fails with `ConfigurationError` naming `ai.decision_model`

#### Scenario: Bridge route keeps chat router off SystemOneModel
- **WHEN** `resolve_pydantic_ai_model("openai-chat:jev-router", settings=...)` runs with a chat provider, and `_model_prefix_and_target("typesafe/jev-router", ai_cfg)` runs with `provider="ollama"`
- **THEN** `_is_jev_decision_name("openai-chat:jev-router")` is `False`, the resolved model is not a `SystemOneModel`, and `_model_prefix_and_target` does not select the gateway route

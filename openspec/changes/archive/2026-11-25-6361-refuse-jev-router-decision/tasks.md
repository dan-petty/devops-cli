# Tasks

## 1. Refuse router names in decision-model validation and bridge routing

> Kind: behavior

- [x] 1.1 Add failing unit tests in `tests/config/test_decision_point_settings.py` and `tests/ai/test_jev.py` covering `is_jev_model_target`, `is_decision_model_name`, `load_settings()` refusal of `typesafe/jev-router`, `_is_jev_decision_name("openai-chat:jev-router")`, `resolve_pydantic_ai_model("openai-chat:jev-router", ...)` not returning `SystemOneModel`, and `_model_prefix_and_target` for `typesafe/jev-router` under `ollama`
  - Verification: `$ uv run pytest -q tests/config/test_decision_point_settings.py tests/ai/test_jev.py`
- [x] 1.2 Replace `CONST_AI_JEV_MODEL_TARGETS` with `CONST_AI_JEV_MODEL_TARGET_RE` in `src/devops_cli/config/constants.py`, add `is_jev_model_target` in `src/devops_cli/config/settings.py`, and use `is_jev_model_target` in `is_decision_model_name` and `src/devops_cli/ai/pydantic_ai_bridge.py`
  - Verification: `$ uv run pytest -q tests/config/test_decision_point_settings.py tests/ai/test_jev.py tests/ai/test_pydantic_ai_profiles_and_providers.py`

Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

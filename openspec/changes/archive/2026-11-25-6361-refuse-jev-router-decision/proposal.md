# Proposal: #6361

## Why

The settings check accepts `typesafe/jev-router` and `jev-router` as a System One decision model because `is_decision_model_name` in `src/devops_cli/config/settings.py` checks only the string prefix `typesafe/jev-` and `jev-`. That same prefix rule causes `_is_jev_decision_name` and `_model_prefix_and_target` in `src/devops_cli/ai/pydantic_ai_bridge.py` to turn a chat router target such as `openai-chat:jev-router` into a `SystemOneModel`, whose requests fail because the router writes text.

## What Changes

- Add `is_jev_model_target` in `src/devops_cli/config/settings.py` using `CONST_AI_JEV_MODEL_TARGET_RE` (`r"^(?:typesafe/)?jev-\d"`) in `src/devops_cli/config/constants.py`, replacing `CONST_AI_JEV_MODEL_TARGETS`.
- Update `is_decision_model_name` to call `is_jev_model_target` so router targets such as `typesafe/jev-router`, `jev-router`, and `openai-chat:jev-router` return `False` while versioned targets such as `typesafe/jev-1.14` and `jev-1.13` continue to return `True`.
- Update `_model_prefix_and_target` and `_is_jev_decision_name` in `src/devops_cli/ai/pydantic_ai_bridge.py` to use `is_jev_model_target` and `is_decision_model_name`, so `openai-chat:jev-router` stays a chat model rather than becoming a `SystemOneModel`.
- Add unit tests in `tests/config/test_decision_point_settings.py` and `tests/ai/test_jev.py`.

## Capabilities

### Modified Capabilities

- `decision-workflows`: Require a digit after `jev-` for unprefixed and prefixed Jev decision-model targets in settings validation and bridge model resolution.

## Impact

- Configuration loading (`Settings` and `load_settings`) refuses `ai.decision_model: typesafe/jev-router`.
- Model resolution (`resolve_pydantic_ai_model`) stops resolving `openai-chat:jev-router` or Ollama `typesafe/jev-router` through the System One / Jev decision path.
- Existing versioned targets (`typesafe/jev-1.14`, `jev-1.13`, `litellm:typesafe/jev-1.14`, `typesafe:jev-1.14`, `system-one:a-decision-model`) remain accepted.

## Feasibility

Verified directly against `origin/main` (`feddcc2d8`):
- `src/devops_cli/config/constants.py:3347` defines `CONST_AI_JEV_MODEL_TARGETS = ("typesafe/jev-", "jev-")`.
- `src/devops_cli/config/settings.py:999-1009` uses `target.startswith(CONST_AI_JEV_MODEL_TARGETS)` and `name.startswith(CONST_AI_JEV_MODEL_TARGETS)`.
- `src/devops_cli/ai/pydantic_ai_bridge.py:68` uses `model_str.startswith(CONST_AI_JEV_MODEL_TARGETS)`, and line `127` calls `is_decision_model_name(name)`.
- `rg CONST_AI_JEV_MODEL_TARGETS` shows no other callers in `src` or `tests`.

## Existing Tool Considered

No open tool or external library validates this repository's internal `typesafe/jev-` vs `jev-router` naming convention; the change replaces two tuple-prefix checks with one small compiled regex helper shared across settings and bridge modules (cost: under 10k tokens and under 1 hour).

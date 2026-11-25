# Design

## Decisions

- **Compiled versioned-target pattern (`CONST_AI_JEV_MODEL_TARGET_RE`)**: Define `r"^(?:typesafe/)?jev-\d"` in `src/devops_cli/config/constants.py` and expose `is_jev_model_target(name: str) -> bool` in `src/devops_cli/config/settings.py`. Requiring a digit right after `jev-` refuses router names such as `jev-router` and `typesafe/jev-router` while accepting versioned targets such as `jev-1.13` and `typesafe/jev-1.14`.
- **Single shared predicate**: Both `is_decision_model_name` in `src/devops_cli/config/settings.py` and `_model_prefix_and_target` in `src/devops_cli/ai/pydantic_ai_bridge.py` call `is_jev_model_target`. `_is_jev_decision_name` delegates to `":" in name and is_decision_model_name(name)`, keeping one copy of the prefix partition rule. Explicit System One prefixes (`system-one:` and `typesafe:`) in `CONST_AI_JEV_SYSTEM_ONE_PREFIXES` continue to identify System One routes such as `system-one:a-decision-model`.
- **Replace tuple constant cleanly**: Because `CONST_AI_JEV_MODEL_TARGETS` has no other callers across `src/` or `tests/`, replace it with `CONST_AI_JEV_MODEL_TARGET_RE` rather than keeping an unused constant.

## Rejected alternatives

- **Duplicate regex in `pydantic_ai_bridge.py` and `settings.py`**: Rejected because two independent checks can drift out of sync.
- **Maintain an explicit denylist for `jev-router`**: Rejected because any future non-versioned Jev chat router name would trigger the same bug.
- **Drop `CONST_AI_JEV_SYSTEM_ONE_PREFIXES`**: Rejected because existing behavior explicitly accepts explicit `system-one:` targets such as `system-one:a-decision-model`.

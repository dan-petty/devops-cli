# Proposal: #4505

## Why

`roadmap.implement.step_token_ceiling` (#4394) has a fixed default: `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`, twice the default step budget. The validator refuses a ceiling below `step_token_budget` (#4505). So a person who sets only the step budget above the fixed ceiling gets a `ValidationError`, and the Service and the runner do not start. A budget below the fixed ceiling but above half of it gets a cut extension: the live budget of 12000000 extends to 16000000 (+33%), not to 18000000 (+50%). Requirement "Ceiling default" of #4394 asks for twice the configured step budget.

## What Changes

- When no config file and no variable sets `step_token_ceiling`, the ceiling is twice the loaded `step_token_budget`. The field is `int | None` with the default None, and the property `token_ceiling` of `RoadmapImplementConfig` gives the ceiling that the step uses. The settings do not store the twice value, so a change of the budget, also by `devops config set`, moves the ceiling and writes no ceiling into the config file.
- `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` goes. `CONST_ROADMAP_IMPLEMENT_CEILING_FACTOR` (2) holds the factor, and the table of the roadmap limits classifies it and keeps the removed name out.
- An explicit ceiling below the budget is still refused, and the message names `step_token_ceiling`. The validator compares only a ceiling that a source sets.
- The description of the setting, `docs/ROADMAP_WORKFLOW.md` and the generated documents state the default.

The default of a setting is behavior that a consumer observes, so the change has a delta for `roadmap-implement-step`.

## Capabilities

- `roadmap-implement-step` (modified): the requirement "The ceiling of a step budget is a setting".

## Impact

- A config file or a variable that sets only `step_token_budget` loads at every value, and the extension gets its whole half of the budget.
- `devops config set roadmap.implement.step_token_budget` accepts every value above the old ceiling, and writes only the budget.
- `devops config show` and `docs/CONFIGURATION.md` show `step_token_ceiling` as None when no source sets it. The description of the setting gives the rule.
- The live ConfigMap sets `step_token_budget: 12000000` and no ceiling. Its ceiling goes from 16000000 to 24000000, so a step that makes progress at its budget extends to 18000000. The ConfigMap needs no change for this item.
- The change fits one pull request.

## Feasibility

- The defect, on `main` at 7234d718: `RoadmapImplementConfig(step_token_budget=12_000_000).step_token_ceiling` is 16000000, and a config file with `step_token_budget: 17000000` and no ceiling fails `load_settings` with `step_token_ceiling must not be below step_token_budget`. The three new tests fail on the base for these causes.
- A first version gave the field a pydantic `default_factory` that reads the validated budget. The review of the pull request found that the factory runs one time, at load. `RoadmapImplementConfig` has `validate_assignment=True`, and `dotted_set` assigns the new budget, so the validator compared it with the old ceiling: `devops config set roadmap.implement.step_token_budget 20000000` failed with `step_token_ceiling must not be below step_token_budget`, and the new test of that command fails on that version.
- A ceiling that the validator writes again at each change would go into the config file: `save_settings` writes each key whose value changed after the load. The next change of the budget above it would then fail again. So the settings keep None, and the property gives the twice value.
- `ci.gate_slots` (`int | None`, resolved where it is read) and the property `ValkeyConfig.endpoint` are the same form in the settings.

## Existing Tool Considered

- pydantic `int | None` with a property covers the need, so the change builds nothing of its own: one property of three lines gives the factor.
- The change deletes `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`.

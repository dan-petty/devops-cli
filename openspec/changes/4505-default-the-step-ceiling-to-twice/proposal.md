# Proposal: #4505

## Why

`roadmap.implement.step_token_ceiling` (#4394) has a fixed default: `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`, twice the default step budget. The validator refuses a ceiling below `step_token_budget` (#4505). So a person who sets only the step budget above the fixed ceiling gets a `ValidationError`, and the Service and the runner do not start. A budget below the fixed ceiling but above half of it gets a cut extension: the live budget of 12000000 extends to 16000000 (+33%), not to 18000000 (+50%). Requirement "Ceiling default" of #4394 asks for twice the configured step budget.

## What Changes

- When no config file and no variable sets `step_token_ceiling`, its default is twice the loaded `step_token_budget`. A pydantic `default_factory` that takes the validated data gives it, so the field stays an `int`.
- `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` goes. `CONST_ROADMAP_IMPLEMENT_CEILING_FACTOR` (2) holds the factor, and the table of the roadmap limits classifies it and keeps the removed name out.
- An explicit ceiling below the budget is still refused, and the message names `step_token_ceiling`.
- The description of the setting, `docs/ROADMAP_WORKFLOW.md` and the generated documents state the default.

The default of a setting is behavior that a consumer observes, so the change has a delta for `roadmap-implement-step`.

## Capabilities

- `roadmap-implement-step` (modified): the requirement "The ceiling of a step budget is a setting".

## Impact

- A config file or a variable that sets only `step_token_budget` loads at every value, and the extension gets its whole half of the budget.
- The live ConfigMap sets `step_token_budget: 12000000` and no ceiling. Its ceiling goes from 16000000 to 24000000, so a step that makes progress at its budget extends to 18000000. The ConfigMap needs no change for this item.
- The change fits one pull request.

## Feasibility

- The defect, on `main` at 7234d718: `RoadmapImplementConfig(step_token_budget=12_000_000).step_token_ceiling` is 16000000, and a config file with `step_token_budget: 17000000` and no ceiling fails `load_settings` with `step_token_ceiling must not be below step_token_budget`. The three new tests fail on the base for these causes.
- pydantic 2.13.5 (the locked version) calls a `default_factory` that takes one argument with the validated data of the fields before it (pydantic 2.10 and later). When the step budget fails its own validation, pydantic does not call the factory and reports `default_factory_not_called`, so the error of the budget still names the budget. A probe of a model with the two fields gave 16 for no input, 34 for a budget of 17, and 9 for an explicit ceiling of 9.
- `CONFIGURATION.md` reads the default from an instance of `Settings`, so it shows the resolved value. `setting_default`, which calls `get_default` with no data, is not called for this key.

## Existing Tool Considered

- pydantic `Field(default_factory=...)` with validated data covers the need, so the change builds nothing of its own: one function of one line gives the factor to the factory.
- The change deletes `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING`.

# Design

## Decisions

- **No stored default.** `step_token_ceiling` is `int | None` with the default None. The property `token_ceiling` gives `step_token_ceiling`, or twice `step_token_budget` when it is None. `StepBudget` is the one reader, and it reads the property. The validator `_token_settings_agree` compares only a ceiling that a source sets: an unset ceiling is twice the budget, so it is never below it. The rule lives in the property only.
- **The factor is a constant.** `CONST_ROADMAP_IMPLEMENT_CEILING_FACTOR` (2) is a rule, not a value that a person tunes: a person tunes the ceiling itself. Twice the budget always leaves room for the extension of half the budget.

## Rejected alternatives

- **A `default_factory` that reads the validated budget.** The factory runs one time, when the model is built. `devops config set` of the budget assigns it with `validate_assignment=True`, and the validator then compared the new budget with the old ceiling and refused it.
- **Write the ceiling again in the after-validator.** An assignment in an after-validator runs the validators again, and a write past it puts the twice value into the dump. `save_settings` then writes it into the config file on the next `devops config set`, and the next change of the budget above it fails.
- **A `mode="before"` validator that fills the ceiling.** It reads the raw input, where a variable gives the budget as text, so it would parse the budget a second time before pydantic validates it. Its value also goes into the dump.

# Design

## Decisions

- **A default factory with the validated data.** `step_token_ceiling` keeps the type `int` and gets `default_factory=_twice_the_step_budget`, which reads `step_token_budget` from the validated data. The field is declared after the budget, so the data holds the loaded budget, from a config file or a variable. Each reader of the field gets an `int`, and the validator `_token_settings_agree` keeps its one comparison.
- **The factor is a constant.** `CONST_ROADMAP_IMPLEMENT_CEILING_FACTOR` (2) is a rule, not a value that a person tunes: a person tunes the ceiling itself. Twice the budget always leaves room for the extension of half the budget.

## Rejected alternatives

- **`int | None` with the default None, resolved in the after-validator.** The model has `validate_assignment=True`, so an assignment in an after-validator runs the validators again. Each reader would also get `int | None` and need a second resolution of the same rule.
- **Resolve None in `StepBudget`.** The loaded settings and `CONFIGURATION.md` would show no ceiling, and the validator could not compare an unset ceiling, so the rule would live in two places.
- **A `mode="before"` validator that fills the ceiling.** It reads the raw input, where a variable gives the budget as text, so it would parse the budget a second time before pydantic validates it.

# roadmap-implement-step/budgets Specification Delta

## ADDED Requirements

### Requirement: Soft-cap extension runs ordered guards and registered decision point
When `roadmap.decisions` configures `implement.extension` (`rule`, `shadow`, or `on`), `StepBudget` and `ToolCallLog` SHALL track repeated identical call-and-answer pairs (`4`) and repeated failing calls (`3`) alongside context window share (`<= 0.75`), step/item time margins, item token headroom, `step_token_ceiling`, and `service_stopping()`. Guards SHALL short-circuit before `rule` and `model` in fixed order, while keeping default behavior intact when `implement.extension` is `off`.

#### Scenario: Loop guard and outer limits prevent unsafe soft-cap extension
- **WHEN** `implement.extension` runs in `Mode.RULE` or `Mode.SHADOW` while `service_stopping()` is true, `value + step > token_ceiling`, `window_share > 0.75`, remaining time is below margin, or `ToolCallLog` observed 4 identical call+answer pairs or 3 identical failing calls
- **THEN** the extension is refused at the first failing guard with `guard` recorded on the decision record and zero model requests sent

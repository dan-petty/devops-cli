## ADDED Requirements

### Requirement: The foreign-change stop carries outside_plan
The stop of an extra repair turn whose turn changed a path outside the allowed set SHALL carry `FailureClass.OUTSIDE_PLAN`, and its class SHALL NOT depend on the path text or the failed check name.

#### Scenario: A foreign path after an extra turn
- **WHEN** an extra repair turn changes a path outside `ask.may_change` and outside the change `tasks.md`
- **THEN** `_extra_turn` returns `_Failure` with `klass` set to `FailureClass.OUTSIDE_PLAN`

#### Scenario: The path text holds classifier words
- **WHEN** the foreign path list holds a word such as `pre-commit` or `ci`
- **THEN** the stop class remains `FailureClass.OUTSIDE_PLAN` and the action is `wait`

## ADDED Requirements

### Requirement: Return clears implement run keys
`apply_return` (used by `devops roadmap return`) SHALL clear implement run keys (`implement.job`, `implement.job_state`, `implement.stopped`, `implement.failure`, `implement.left_action`, `implement.check`, `implement.branch`, `implement.pr`, and related run delivery keys) by default when returning an item to `New`, while runner-pod premise returns keep `implement.job` via `clear_implement=False` until Job reporting finishes.

#### Scenario: Manual return clears the implement record
- **WHEN** an item holds `implement.job`, `implement.stopped`, `implement.failure`, `implement.branch`, and `implement.pr` and `apply_return` runs from `plan_return`
- **THEN** those implement keys are cleared from the returned item's job record

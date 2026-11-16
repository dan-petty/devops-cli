## ADDED Requirements

### Requirement: Explain names the state of a stopped item
When the job record of the item holds `implement.stopped`, `devops roadmap explain` SHALL print the step that stopped it, the class of the failure, the number of attempts of the stopped step, the kept work and the action left, from the record alone.

#### Scenario: A stopped item with a class, kept work and an action left
- **WHEN** The record holds `implement.stopped`, `implement.failure` with `types`, `implement.left_action` with `wait`, `implement.wip` with group 2 and 3 of 5 tasks, and `implement.trace` holds two attempt events of the stopped step.
- **THEN** The report of `devops roadmap explain` names `types`, the count of 2, group 2 with 3 of 5 tasks, and `wait`.

#### Scenario: A stop with no class and no action left on record
- **WHEN** The record holds `implement.stopped` and neither `implement.failure` nor `implement.left_action`.
- **THEN** The report states that the record holds no class and no action left, and it still prints the line of the stop.

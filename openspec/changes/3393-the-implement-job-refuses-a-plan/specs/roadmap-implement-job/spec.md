## ADDED Requirements

### Requirement: The job leaves out an item whose plan fails the check
The implement selection SHALL run `check_proposal` on the plan of a Staged or Planned item before it returns a target, and it SHALL leave the item out with the first problem as its reason when the check returns problems.

#### Scenario: A Staged item with a placeholder task
- **WHEN** The branch of a Staged item holds a plan with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target for the item and its reason holds the first problem.

#### Scenario: A Planned item with a placeholder task
- **WHEN** The default branch holds the plan of a Planned item with the placeholder task `1.1 x`.
- **THEN** `plan_implement` returns no target and makes no branch for the item.

#### Scenario: A plan that passes the check
- **WHEN** The plan of the item passes every `check_proposal` gate.
- **THEN** `plan_implement` returns the item as a target.

#### Scenario: A plan with two problems
- **WHEN** The plan returns two or more problems and the job leaves the item out.
- **THEN** The reason of the item holds the first problem and no later problem.

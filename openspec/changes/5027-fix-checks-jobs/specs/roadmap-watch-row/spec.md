## MODIFIED Requirements

### Requirement: The due_steps pure function routes pull request states
`due_steps(state)` SHALL evaluate pull request states and return due lifecycle actions. It SHALL skip a pull request whose item has a live unit: a runner Job that no round reported, or the check-out of a stage Job. A FAILED bot pull request whose failed check has the class test, lint, types or plan check SHALL get `fix_checks`, with the check that holds the cause; a `ci_infra` failure and a cancelled check SHALL get no `fix_checks`.

#### Scenario: Bot pull request is ready
- **WHEN** a bot pull request has all checks passing
- **THEN** `due_steps` returns the `ready` step

#### Scenario: Person pull request has a conflict
- **WHEN** a person pull request has merge conflicts with the default branch
- **THEN** `due_steps` returns the `comment_conflict` step

#### Scenario: Pull request is merged or closed
- **WHEN** a pull request is merged or closed
- **THEN** `due_steps` returns `status_sync` (and `cleanup` if it is a plan)

#### Scenario: A bot pull request with a failed test check
- **WHEN** a bot pull request has a failed `Tests & Coverage (shard 2)` check and a failed `Tests & Coverage` check
- **THEN** `due_steps` returns `fix_checks`, and the check of the unit is the shard

#### Scenario: A failed title check gets no fix unit
- **WHEN** a bot pull request has a failed `Semantic PR title` check
- **THEN** `due_steps` returns `comment_ci_infra` and no `fix_checks`

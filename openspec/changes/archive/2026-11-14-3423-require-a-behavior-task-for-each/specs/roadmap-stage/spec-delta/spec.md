## ADDED Requirements

### Requirement: A scenario that names no code has a behavior task
`check_proposal` SHALL refuse a scenario of an added or modified requirement that names no code in a code span when no behavior group covers it. A behavior group covers a scenario when its `test` holds the scenario name or the requirement name, or when its `verify` runs a test module that the group changes or creates. A scenario whose name the base spec of the capability already holds SHALL be exempt. The problem SHALL name the scenario and the requirement.

#### Scenario: A scenario that names only a field
- **WHEN** a plan modifies a requirement, adds the scenario `A What Changes line below the least length`, and its only behavior group tests another rule
- **THEN** `check_proposal` returns one problem that names the scenario and the requirement

#### Scenario: A task that names the scenario
- **WHEN** a behavior group's `test` text holds the name of the scenario or of its requirement
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A verify command that runs the changed test module
- **WHEN** a behavior group changes or creates a test module under `tests/` and its `verify` runs that module
- **THEN** `check_proposal` returns no problem for the scenario

#### Scenario: A scenario of the base spec
- **WHEN** a plan restates in a MODIFIED requirement a scenario that the base spec of the capability already holds
- **THEN** `check_proposal` returns no problem for that scenario

### Requirement: The stage prompt asks for a behavior task for each new scenario
The stage prompt SHALL tell the planner that each scenario of an added or modified requirement that names no code needs a behavior group whose `test` names the scenario or the requirement, or whose `verify` runs a changed or created test module, and that a base-spec scenario is exempt.

#### Scenario: The prompt holds the rule
- **WHEN** a test reads the text of `roadmap_stage_change.md`
- **THEN** the text holds the sentence of the rule

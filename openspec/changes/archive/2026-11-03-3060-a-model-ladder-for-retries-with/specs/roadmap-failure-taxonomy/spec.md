## MODIFIED Requirements

### Requirement: The action left
`left_action` SHALL give the default action of the class, or `wait` when the action taken is that default.

#### Scenario: A repair that did not work
- **WHEN** the class is `types` and the job took `repair`
- **THEN** the action left is `wait`

#### Scenario: A tier change that did not work
- **WHEN** the class is `parser` and the job took `change_tier`
- **THEN** the action left is `wait`

#### Scenario: No action taken
- **WHEN** the class is `oom` and the job took no action
- **THEN** the action left is `raise_limit`

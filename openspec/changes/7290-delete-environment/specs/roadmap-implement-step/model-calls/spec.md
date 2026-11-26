## ADDED Requirements

### Requirement: The settings refuse a step call deadline above the step limit
The settings SHALL refuse a `roadmap.implement.request_timeout_seconds` above `roadmap.implement.step_time_limit_seconds`.

#### Scenario: A deadline above the step limit
- **WHEN** the config sets `roadmap.implement.request_timeout_seconds` above `roadmap.implement.step_time_limit_seconds`
- **THEN** the settings load fails with an error that names both settings

## REMOVED Requirements

### Requirement: The deadline of a step call nests between the router timeout and the step limit
**Reason**: The router timeout is in the gateway config of the environment repository (#7290).
**Migration**: See `The settings refuse a step call deadline above the step limit`.

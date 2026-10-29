## ADDED Requirements

### Requirement: The Service limits its model calls to a configured count in flight
The Service SHALL keep at most `service.model_call_concurrency` model calls in flight at once, default 1, and a lane that cannot take a slot SHALL wait in the Service's process, where no stall timer runs, until it takes one. The Service SHALL set the limit from its setting at start.

#### Scenario: Two lanes send a model call at the same time
- **WHEN** the Service has a limit of 1, two lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most one call is in flight at once, and both calls finish

#### Scenario: A lane waits for a held slot
- **WHEN** the Service has a limit of 1, one call holds the slot, and a lane sends a model call
- **THEN** the lane waits in the process and sends its call once the other call releases the slot

#### Scenario: The limit is raised
- **WHEN** the Service has a limit of 2, four lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most two calls are in flight at once, and all four calls finish

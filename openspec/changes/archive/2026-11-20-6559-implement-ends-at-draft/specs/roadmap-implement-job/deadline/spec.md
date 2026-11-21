## MODIFIED Requirements

### Requirement: The default stall covers the silent waits of the runner
The default stall SHALL be at least 600 seconds above the longest wait in which the runner writes no log line, and the default extension SHALL be at least the stall plus the interval of the `implement` row plus the interval of a tick of the Service.

#### Scenario: The defaults cover the silent waits
- **WHEN** a test reads the constants of the runner
- **THEN** the default stall is at least the longest of the command timeout and the model call timeout plus 600 seconds, and the default extension is at least the stall plus the interval of the row and the tick of the Service

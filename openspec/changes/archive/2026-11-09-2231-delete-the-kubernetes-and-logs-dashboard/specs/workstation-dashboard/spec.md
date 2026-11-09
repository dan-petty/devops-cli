## Purpose
The workstation terminal user interface dashboard provides real-time situational awareness across Docker, Telemetry, and Valkey subsystems.

## MODIFIED Requirements

### Requirement: Dashboard tab validation
The `devops dashboard` command SHALL validate the `--tab` option value at the command boundary against configured dashboard domains (docker, telemetry, valkey) and numeric indexes (1=docker, 2=telemetry, 3=valkey). When the value names no configured tab, the command SHALL exit with status 1 and emit a message naming the valid tab values without a Python traceback.

#### Scenario: Unknown tab value is rejected
- **WHEN** an operator executes `devops dashboard --tab nope`
- **THEN** the command exits with status 1
- **AND** the error output names the valid tab values
- **AND** no exception traceback is displayed

## ADDED Requirements

### Requirement: Roadmap age gauges are declared instruments
The age-of-oldest-item gauges for the states new, ready, planned, in-progress, in-review and blocked, and the age-of-oldest-claim gauge, SHALL be entries of INSTRUMENTS in src/devops_cli/telemetry/instruments.py and SHALL be sent through emit().

#### Scenario: The registry holds the age gauges
- **WHEN** The telemetry module is imported and INSTRUMENTS is read
- **THEN** The gauges for the six states and the claim gauge are present, each a gauge whose name starts with devops_cli_ and ends in _seconds

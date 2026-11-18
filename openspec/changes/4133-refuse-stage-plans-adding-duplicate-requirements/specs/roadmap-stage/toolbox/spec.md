## ADDED Requirements

### Requirement: The tool read_spec lists the scenario of each requirement
The `read_spec` tool SHALL list, for a capability, the name of each requirement with the name of each of its scenarios. It SHALL also list the change, the requirement name and the scenario names of each requirement that another active change adds or modifies for that capability.

#### Scenario: A capability with two requirements
- **WHEN** The planner calls the tool for a capability whose two requirements each hold one scenario.
- **THEN** The answer names each requirement and the name of its scenario.

#### Scenario: An active change modifies one requirement
- **WHEN** An active change modifies a requirement of the capability.
- **THEN** The answer names the change, the requirement and the name of its scenario.

#### Scenario: A removed requirement is no candidate
- **WHEN** An active change removes a requirement of the capability.
- **THEN** The answer lists no requirement of that change.

## ADDED Requirements

### Requirement: The implementation role holds no threat-intelligence lookup
The implementation role MUST NOT hold `security_intel_network` or `security_intel_package`, the two tools that send a value the model gives to a threat-intelligence service outside the project.

#### Scenario: The implementation role holds no security lookup
- **WHEN** A test calls `tools_for_role` for the implementation role with the catalogue of the server.
- **THEN** The returned names hold neither `security_intel_network` nor `security_intel_package`, and the role holds 15 tools.

#### Scenario: The planning and review roles keep the lookups
- **WHEN** A test calls `tools_for_role` for the planning role and for the review role.
- **THEN** Each returned list holds `security_intel_network` and `security_intel_package`.

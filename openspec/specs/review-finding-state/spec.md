# review-finding-state Specification

## Purpose
Stores, validates and displays the lifecycle state and confirmation adjudicator of admitted review findings across session files and CLI reports.

## Requirements

### Requirement: Human valid verdict confirms admitted finding
When a person records a VERIFIED or MITIGATED verdict on an admitted finding that has a fingerprint v2, the system SHALL store its lifecycle state as CONFIRMED and record its confirmation adjudicator as human.

#### Scenario: Person records VERIFIED verdict
- **WHEN** A person records a VERIFIED verdict on an admitted finding with a fingerprint v2
- **THEN** The finding lifecycle state is CONFIRMED and confirmed_by is set to "human" in session files

#### Scenario: Person records MITIGATED verdict
- **WHEN** A person records a MITIGATED verdict on an admitted finding with a fingerprint v2
- **THEN** The finding lifecycle state is CONFIRMED and confirmed_by is set to "human" in session files

### Requirement: Overturning verdict moves finding back to OPEN
When a person records an UNVERIFIED or INVALIDATED verdict on a CONFIRMED finding, the system SHALL set its lifecycle state to OPEN and clear the confirmation adjudicator.

#### Scenario: Person invalidates confirmed finding
- **WHEN** A person records an INVALIDATED verdict on a CONFIRMED finding
- **THEN** The finding lifecycle state moves to OPEN and confirmed_by is cleared to None

#### Scenario: Person resets confirmed finding to UNVERIFIED
- **WHEN** A person records an UNVERIFIED verdict on a CONFIRMED finding
- **THEN** The finding lifecycle state moves to OPEN and confirmed_by is cleared to None

### Requirement: Lifecycle state transitions allow CONFIRMED to OPEN
The finding lifecycle state transition table SHALL allow transition from CONFIRMED to OPEN when a human verdict changes.

#### Scenario: Transition check allows CONFIRMED to OPEN
- **WHEN** can_transition is evaluated from FindingState.CONFIRMED to FindingState.OPEN
- **THEN** It returns True

### Requirement: Findings command displays finding state
`devops review findings --details` SHALL display the finding lifecycle state in finding detail panels.

#### Scenario: User inspects finding details
- **WHEN** A user runs `devops review findings --details` on a session containing findings
- **THEN** The output panel contains the finding lifecycle state

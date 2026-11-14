## ADDED Requirements

### Requirement: The system topology dashboard shows overview stat panels
The system topology dashboard SHALL provide a "System Overview" row with panels of type `stat`. These panels SHALL display tunnel connections, ingress request volume, AI gateway health, and autonomous brain decisions.

#### Scenario: The dashboard contains summary stat panels
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** it contains a row titled "System Overview"
- **AND** it contains at least 4 panels of type `stat`

### Requirement: The system topology dashboard shows state timeline and status history panels
The system topology dashboard SHALL provide a "Component State & Status History" row. It SHALL contain at least one panel of type `state-timeline` and at least one panel of type `status-history` to track service availability and knowledge drift over time.

#### Scenario: The dashboard contains timeline and history panels
- **WHEN** the dashboard `system-topology.json` is loaded
- **THEN** it contains a row titled "Component State & Status History"
- **AND** it contains at least one panel of type `state-timeline`
- **AND** it contains at least one panel of type `status-history`

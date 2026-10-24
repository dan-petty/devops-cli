# survey Specification

## Purpose
Inspects upstream maintenance signals for pinned runtime dependencies and compares devops-cli capabilities against configured comparable tools.

## Requirements

### Requirement: Upstream dependency maturity reporting
The system SHALL inspect each pinned runtime dependency from the project configuration and report last commit date, release cadence, archival status, licence, and a calculated maintenance score.

#### Scenario: Pinned dependencies emit all four signals
- **WHEN** the survey command executes
- **THEN** every dependency entry contains last commit date, release cadence, archival status, and licence fields

### Requirement: Comparable tools capability comparison
The system SHALL compare capabilities against configured comparable tools and report status as present, absent, or unknown.

#### Scenario: Capabilities are assessed across configured tools
- **WHEN** the survey command evaluates configured comparable tools
- **THEN** each capability row indicates whether the feature is present, absent, or unknown

### Requirement: Citation verification for comparable tools
The system SHALL require and output a citation URL or document reference for every capability row of a comparable tool.

#### Scenario: Every comparable tool row includes a citation
- **WHEN** the survey report is generated
- **THEN** no capability row for a comparable tool lacks a non-empty citation field

### Requirement: Default to unknown for unassessed capabilities
The system SHALL record an unassessed capability for a comparable tool as unknown and never as absent.

#### Scenario: Unassessed capability reports unknown status
- **WHEN** a comparable tool configuration omits status assessment for a capability
- **THEN** the survey output reports unknown for that tool capability

### Requirement: Capability gaps emitted to roadmap intake
The system SHALL identify features present in a comparable tool and absent in devops-cli as capability gaps and hand them to roadmap intake.

#### Scenario: Detected gap generates intake candidate
- **WHEN** candidate emission is requested for a detected capability gap
- **THEN** the survey hands a new candidate with source citation to roadmap intake

### Requirement: Structured machine-readable survey report
The system SHALL run as a CLI command and emit a structured report in JSON or terminal table format.

#### Scenario: JSON format requested
- **WHEN** the survey command runs with the json option
- **THEN** it exits with code 0 and emits structured JSON containing dependencies and capabilities

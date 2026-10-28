## MODIFIED Requirements

### Requirement: JSON stdout parses
The system SHALL write a single valid JSON document to stdout for `devops scan trivy`, `scan secrets`, `scan sast`, `scan complexity`, `scan workflows` and `scan aibom` when `--json` or `--format json` is set, and SHALL NOT print a progress line to stdout in that mode.

#### Scenario: JSON flag
- **WHEN** the user runs `devops scan trivy . --json`
- **THEN** stdout is a single valid JSON document and the command exits 0

#### Scenario: Format option
- **WHEN** the user runs `devops scan workflows . --format json`
- **THEN** stdout is a single valid JSON document and the command exits 0

#### Scenario: AIBOM format option
- **WHEN** the user runs `devops scan aibom . --format json` without `--output`
- **THEN** stdout is a single valid JSON document and the command exits 0

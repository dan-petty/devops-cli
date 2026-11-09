## ADDED Requirements

### Requirement: Static security analysis runs Gitleaks once per review
The review SHALL run Gitleaks once for all reviewed scannable files over a temporary scratch directory holding the materialized target files, and map each finding back to its reviewed file.

#### Scenario: Review of multiple scannable files
- **WHEN** a review runs static security analysis on N files that need a secret scan
- **THEN** Gitleaks executes exactly once over the materialized targets directory
- **AND** each finding location names the original reviewed file and not the scratch directory

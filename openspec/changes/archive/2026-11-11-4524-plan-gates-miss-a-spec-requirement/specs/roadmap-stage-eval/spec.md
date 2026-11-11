## ADDED Requirements

### Requirement: The golden set holds the plan with a requirement text over the OpenSpec limit
The golden set SHALL hold the plan of pull request #4435 as a case whose `issue` is 3462, with one `spec_delta_wrong` defect at the gate `paths`: its MODIFIED requirement text has 543 characters.

#### Scenario: The replay catches the long requirement
- **WHEN** `uv run devops roadmap eval stage --replay` runs on the whole set
- **THEN** the defect of the case of #3462 is caught by the gate `paths`, and the command exits 0

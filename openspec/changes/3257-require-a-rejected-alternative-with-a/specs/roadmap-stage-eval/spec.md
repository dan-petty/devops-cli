## ADDED Requirements

### Requirement: The golden set holds a plan with no rejected alternative
The stage golden set SHALL hold one case from the plan that pull request 3168 staged, whose plan states a decision and no rejected alternative with a fact, and the replay SHALL catch its defect at the content gate.

#### Scenario: The replay catches the alternatives defect of the new case
- **WHEN** The replay runs the golden set
- **THEN** The content gate catches the defect of the case whose pull is 3168 and reports no stale case

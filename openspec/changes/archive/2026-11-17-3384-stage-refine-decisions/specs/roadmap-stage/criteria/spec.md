## ADDED Requirements

### Requirement: Refine design kept in stage plan
When the issue body holds a refine block with at least one `Chosen` or `Rejected` line, `check_proposal` SHALL refuse a plan whose `decisions` or `rejected` list is empty.

#### Scenario: Refine block with decisions and alternatives
- **WHEN** the issue body holds a refine block with two `Chosen` decisions and one `Rejected` alternative, and the plan holds no decision and no rejected alternative
- **THEN** `check_proposal` returns problems for the missing decisions and rejected alternatives

#### Scenario: Plan with decisions and alternatives
- **WHEN** the issue body holds a refine block with two `Chosen` decisions and one `Rejected` alternative, and the plan holds one decision and one rejected alternative
- **THEN** `check_proposal` returns no problem for the decisions and rejected alternatives

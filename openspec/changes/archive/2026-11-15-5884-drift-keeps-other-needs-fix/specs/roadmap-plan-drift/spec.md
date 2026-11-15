## MODIFIED Requirements

### Requirement: Remove the label after a passing check
The Service SHALL remove the label `plan/needs-fix` from a plan pull request when a later drift check reports no problem, only when the drift row added the label and the last plan comment of the item lists no open finding. A label that another check added SHALL stay.

#### Scenario: A previously failing plan passes
- **WHEN** the drift row added the label `plan/needs-fix` to a plan pull request, and a later drift check reports no problem
- **THEN** the pull request does not have the label `plan/needs-fix`

#### Scenario: A label of the stage review stays
- **WHEN** a plan pull request has the label `plan/needs-fix` from the stage review, it has no drift comment, and the drift check reports no problem
- **THEN** the pull request keeps the label `plan/needs-fix`

#### Scenario: A label held before the drift stays
- **WHEN** a plan pull request had the label `plan/needs-fix` at its first drift check with a problem, and a later drift check reports no problem
- **THEN** the pull request keeps the label `plan/needs-fix`

#### Scenario: An open finding of the plan comment keeps the label
- **WHEN** the drift row added the label `plan/needs-fix`, the last plan comment of the item lists an open finding, and a later drift check reports no problem
- **THEN** the pull request keeps the label `plan/needs-fix`

## ADDED Requirements

### Requirement: Mark a passing plan in the drift comment
The Service SHALL change the drift comment of a plan pull request to the claim `cleared` when a later drift check reports no problem, and a comment with the claim `cleared` SHALL cause no label change.

#### Scenario: A later label of another check
- **WHEN** a plan pull request passed a drift check after a problem, another check then adds the label `plan/needs-fix`, and a later drift check reports no problem
- **THEN** the pull request keeps the label `plan/needs-fix` and the drift row does not change its comment

## MODIFIED Requirements

### Requirement: Label a failing plan pull request
The Service SHALL add the label `verdict/fix-plan` to a plan pull request when the drift check reports at least one problem.

#### Scenario: The drift check reports a problem
- **WHEN** the drift check returns one or more problems for an open plan pull request
- **THEN** the pull request has the label `verdict/fix-plan`

### Requirement: Remove the label after a passing check
The Service SHALL remove the label `verdict/fix-plan` from a plan pull request when a later drift check reports no problem, only when the drift row added the label and the last plan comment of the item lists no open finding. A label that another check added SHALL stay.

#### Scenario: A previously failing plan passes
- **WHEN** the drift row added the label `verdict/fix-plan` to a plan pull request, and a later drift check reports no problem
- **THEN** the pull request does not have the label `verdict/fix-plan`

#### Scenario: A label of the stage review stays
- **WHEN** a plan pull request has the label `verdict/fix-plan` from the stage review, it has no drift comment, and the drift check reports no problem
- **THEN** the pull request keeps the label `verdict/fix-plan`

#### Scenario: A label held before the drift stays
- **WHEN** a plan pull request had the label `verdict/fix-plan` at its first drift check with a problem, and a later drift check reports no problem
- **THEN** the pull request keeps the label `verdict/fix-plan`

#### Scenario: An open finding of the plan comment keeps the label
- **WHEN** the drift row added the label `verdict/fix-plan`, the last plan comment of the item lists an open finding, and a later drift check reports no problem
- **THEN** the pull request keeps the label `verdict/fix-plan`

### Requirement: Block readiness for a failing plan
The `stage_ready` row MUST NOT mark a plan pull request ready while it has the label `verdict/fix-plan`.

#### Scenario: Green checks with the needs-fix label
- **WHEN** a draft plan pull request has passing checks and the label `verdict/fix-plan`
- **THEN** the `stage_ready` row leaves the pull request as a draft

### Requirement: Mark a passing plan in the drift comment
The Service SHALL change the drift comment of a plan pull request to the claim `cleared` when a later drift check reports no problem, and a comment with the claim `cleared` SHALL cause no label change.

#### Scenario: A later label of another check
- **WHEN** a plan pull request passed a drift check after a problem, another check then adds the label `verdict/fix-plan`, and a later drift check reports no problem
- **THEN** the pull request keeps the label `verdict/fix-plan` and the drift row does not change its comment

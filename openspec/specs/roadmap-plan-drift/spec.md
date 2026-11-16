# roadmap-plan-drift Specification

## Purpose
The plan drift row: the Service checks each open plan pull request against the default branch, labels a drifted plan `verdict/fix-plan`, and keeps one comment with each problem.

## Requirements

### Requirement: Detect drift on open plan pull requests
The Service SHALL evaluate each open plan pull request against the head commit of the default branch.

#### Scenario: A stale plan cites a moved path
- **WHEN** an open plan pull request cites a path that the default branch head does not hold
- **THEN** the drift check reports a problem for that path

### Requirement: Recognize a plan pull request
The Service SHALL treat an open pull request whose base is the default branch and whose title or body has the plan form as a plan pull request.

#### Scenario: A delivery is not a plan
- **WHEN** an open pull request into the default branch holds the title and body of a delivery
- **THEN** the drift check reports no problem for it

### Requirement: Run the drift row in the status lane
The status lane SHALL run a `plan_drift` row before the `stage_ready` row on each round.

#### Scenario: A status-lane round starts
- **WHEN** a status-lane round starts for a repository
- **THEN** the round runs `plan_drift` before `stage_ready`

### Requirement: Keep the drift check model-free
The `plan_drift` row MUST run without a model call.

#### Scenario: The drift row runs
- **WHEN** the `plan_drift` row runs on a status-lane round
- **THEN** the row makes no model call

### Requirement: Label a failing plan pull request
The Service SHALL add the label `plan/needs-fix` to a plan pull request when the drift check reports at least one problem.

#### Scenario: The drift check reports a problem
- **WHEN** the drift check returns one or more problems for an open plan pull request
- **THEN** the pull request has the label `plan/needs-fix`

### Requirement: Comment each detected problem
The Service SHALL post a comment on a failing plan pull request that lists each problem the drift check reports.

#### Scenario: The drift check reports two problems
- **WHEN** the drift check returns two problems for an open plan pull request
- **THEN** the comment contains the message of each problem

### Requirement: Keep one drift comment
The Service SHALL keep one drift comment per pull request and update it when the problem list changes.

#### Scenario: The problem list changes
- **WHEN** a plan pull request already has a drift comment and a later drift check reports a different problem list
- **THEN** the Service updates the existing drift comment and creates no second drift comment

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

### Requirement: Block readiness for a failing plan
The `stage_ready` row MUST NOT mark a plan pull request ready while it has the label `plan/needs-fix`.

#### Scenario: Green checks with the needs-fix label
- **WHEN** a draft plan pull request has passing checks and the label `plan/needs-fix`
- **THEN** the `stage_ready` row leaves the pull request as a draft

### Requirement: Cover drift behavior with unit tests
The change MUST add unit tests for drift detection, label changes and comment generation.

#### Scenario: The drift unit tests run
- **WHEN** the unit test suite runs the roadmap stage tests
- **THEN** the suite passes with tests for a detected problem, a label addition, a label removal and a comment body

### Requirement: Mark a passing plan in the drift comment
The Service SHALL change the drift comment of a plan pull request to the claim `cleared` when a later drift check reports no problem, and a comment with the claim `cleared` SHALL cause no label change.

#### Scenario: A later label of another check
- **WHEN** a plan pull request passed a drift check after a problem, another check then adds the label `plan/needs-fix`, and a later drift check reports no problem
- **THEN** the pull request keeps the label `plan/needs-fix` and the drift row does not change its comment

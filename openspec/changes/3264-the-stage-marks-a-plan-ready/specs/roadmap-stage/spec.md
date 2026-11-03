## ADDED Requirements

### Requirement: An open finding keeps the plan in draft
When the verification pass returns a finding that has a quote in its input and a defect type of `missing_path`, `false_premise`, `ignores_existing_code`, `spec_delta_wrong` or reports a placeholder, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `plan/needs-fix`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `plan/needs-fix` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `plan/needs-fix` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

### Requirement: A plan with an open finding is a failed attempt
An item whose plan carries an open finding SHALL NOT count as a staged plan in the round budget of the Service, and its result SHALL be recorded as a failed attempt of failure class `plan_defect`.

#### Scenario: The round counts a plan with an open finding
- **WHEN** The stage records an open finding for an item and the Service counts the round.
- **THEN** The round budget counts no staged plan for the item, and the failure record of the item has class `plan_defect`.

## MODIFIED Requirements

### Requirement: The Service marks a green stage pull request ready
The row `stage_ready` of the Service SHALL mark a staged draft pull request ready when every check of the draft has passed and the pull request holds no label `plan/needs-fix`, and it SHALL leave the pull request in draft with a comment that names the open finding when the label is present.

#### Scenario: Every check passed
- **WHEN** Every check of a staged draft pull request has passed, the pull request holds no `plan/needs-fix` label, and the item is Ready with no Job on it.
- **THEN** The row marks the pull request ready.

#### Scenario: A check failed, a check runs, or no check exists
- **WHEN** A check of the staged draft pull request failed, is still running, or the pull request has no check at all.
- **THEN** The row makes no mark and leaves the pull request in draft.

#### Scenario: A draft of a person
- **WHEN** The draft pull request of a staged item was opened by a person rather than by the stage job.
- **THEN** The row makes no mark.

#### Scenario: The same pull request twice
- **WHEN** The row marks a staged draft pull request ready and reads it again with every check still passed.
- **THEN** The row makes no second mark.

#### Scenario: A pull request that left the draft state
- **WHEN** The pull request of a staged item is no longer a draft.
- **THEN** The row makes no mark.

#### Scenario: No recorded draft
- **WHEN** The record of the item holds no draft pull request.
- **THEN** The row makes no mark and reports nothing.

#### Scenario: A Job works on the item
- **WHEN** A runner Job holds the item, or its Status is In Progress or In Review.
- **THEN** The row makes no mark.

#### Scenario: One item fails
- **WHEN** The mark of one item fails.
- **THEN** The row reports that item and goes on with the other items.

#### Scenario: The check runs only
- **WHEN** The row runs with the checks turned off.
- **THEN** The row still refuses to mark a pull request that holds `plan/needs-fix` and still marks a green pull request that does not.

#### Scenario: A green draft with an open finding stays in draft
- **WHEN** Every check of a staged draft pull request has passed and the pull request holds the label `plan/needs-fix`.
- **THEN** The row leaves the pull request in draft and posts a comment that names the label as the reason.

#### Scenario: The row reads the labels before it marks
- **WHEN** The row reads a pull request whose labels the request does not carry.
- **THEN** The row makes no mark and stops on the read, as it does on a rate limit.

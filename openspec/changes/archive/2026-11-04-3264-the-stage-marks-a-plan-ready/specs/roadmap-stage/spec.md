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

### Requirement: The row refuses a plan with an open finding
The row `stage_ready` SHALL NOT mark a pull request that holds the label `plan/needs-fix`. It SHALL leave that draft and comment once that the label is the reason, and it SHALL record `stage.needs_fix` with the number of the pull request.

#### Scenario: A green draft with an open finding stays in draft
- **WHEN** every check of a staged draft pull request has passed and the pull request holds the label `plan/needs-fix`
- **THEN** the row leaves the pull request in draft and posts a comment that names the label as the reason

#### Scenario: The row states the reason once
- **WHEN** two rounds read a green draft pull request that holds `plan/needs-fix`
- **THEN** the first round posts one comment that names the label and records `stage.needs_fix`, and the second round makes no second comment

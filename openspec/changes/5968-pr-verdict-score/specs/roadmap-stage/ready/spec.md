## MODIFIED Requirements

### Requirement: The row refuses a plan with an open finding
The row `stage_ready` SHALL NOT mark a pull request that holds the label `verdict/fix-plan`. It SHALL leave that draft and comment once that the label is the reason, and it SHALL record `stage.needs_fix` with the number of the pull request.

#### Scenario: A green draft with an open finding stays in draft
- **WHEN** every check of a staged draft pull request has passed and the pull request holds the label `verdict/fix-plan`
- **THEN** the row leaves the pull request in draft and posts a comment that names the label as the reason

#### Scenario: The row states the reason once
- **WHEN** two rounds read a green draft pull request that holds `verdict/fix-plan`
- **THEN** the first round posts one comment that names the label and records `stage.needs_fix`, and the second round makes no second comment

### Requirement: An open finding keeps the plan in draft
When the last review of a plan returns a finding on a place that the plan or the issue holds, with a quote in its input or in a tool answer of the run and a type of `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`, or with a placeholder that its request holds, the stage SHALL keep the plan pull request in draft, apply the label `verdict/fix-plan` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `verdict/fix-plan`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `verdict/fix-plan` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `verdict/fix-plan` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

#### Scenario: An open task order finding
- **WHEN** The last review returns a `task_order` finding whose quote is in the input.
- **THEN** The plan pull request is a draft and it holds the label `verdict/fix-plan`.

#### Scenario: A placeholder only in a tool answer
- **WHEN** The verifier reports a placeholder whose quote is in a tool answer and not in its request.
- **THEN** The finding is not open.

#### Scenario: A quoted dropped criterion finding is open
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in the issue.
- **THEN** `open_findings` returns the finding.

#### Scenario: An unquoted dropped criterion finding is advice
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in none of the issue, the plan and the cited files.
- **THEN** `open_findings` returns no finding.

#### Scenario: A test-only group with no code
- **WHEN** A group of a plan changes only a fixture file and a test file, no group changes the code that its criterion needs, and the verification reply holds a `criterion_dropped` finding that quotes the criterion of the issue.
- **THEN** `open_findings` returns the finding, and the finding returns the plan to the planner while a repair round remains.

#### Scenario: A finding on a requirement that the plan does not change
- **WHEN** The last review returns a `spec_delta_wrong` finding that quotes a base spec from a tool answer and names a requirement that the spec delta of the plan does not hold.
- **THEN** `open_findings` returns no finding.

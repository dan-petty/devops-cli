## ADDED Requirements

### Requirement: The verification prompt separates a dropped criterion from a test-only group that delivers its criterion
The prompt of the verification pass SHALL define `criterion_dropped` for a criterion whose group changes only test files while no group of the plan changes the code or the data that the criterion needs, and SHALL say that a group which changes only test files and tests code of an earlier group is no `criterion_dropped`.

#### Scenario: The prompt names the test-only group
- **WHEN** The prompt of the verification pass is read.
- **THEN** The line of `criterion_dropped` names a group that changes only test files, names the earlier group that changes the code, and says that such a group is no `criterion_dropped`.

## MODIFIED Requirements

### Requirement: An open finding keeps the plan in draft
When the last review of a plan returns a finding that has a quote in its input or in a tool answer of the run and a defect type of `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`, or a finding that reports a placeholder with a quote in its request, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `plan/needs-fix`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `plan/needs-fix` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `plan/needs-fix` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

#### Scenario: An open task order finding
- **WHEN** The last review returns a `task_order` finding whose quote is in the input.
- **THEN** The plan pull request is a draft and it holds the label `plan/needs-fix`.

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
- **THEN** `open_findings` returns the finding and `returning` returns none.

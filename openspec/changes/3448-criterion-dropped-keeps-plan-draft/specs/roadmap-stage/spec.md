## ADDED Requirements

### Requirement: A dropped criterion finding keeps the plan in draft
When the verification pass returns a finding of type `criterion_dropped` that has a quote in its input, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put the finding at the top of the stage comment. The finding SHALL NOT send the plan back to the planner.

#### Scenario: A quoted dropped criterion finding is open
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in the issue.
- **THEN** `open_findings` returns the finding.

#### Scenario: An unquoted dropped criterion finding is advice
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in none of the issue, the plan and the cited files.
- **THEN** `open_findings` returns no finding.

#### Scenario: A test-only group with no code
- **WHEN** The last group of a plan changes only a fixture file and a test file, and the verification reply holds a `criterion_dropped` finding that quotes the criterion of the issue.
- **THEN** `open_findings` returns the finding and `returning` returns none.

### Requirement: The verification prompt separates a dropped criterion from a test-only group that delivers its criterion
The prompt of the verification pass SHALL define `criterion_dropped` for a criterion whose group changes only test files while no group of the plan changes the code or the data that the criterion needs, and SHALL say that a group which changes only test files and tests code of an earlier group is no `criterion_dropped`.

#### Scenario: The prompt names the test-only group
- **WHEN** The prompt of the verification pass is read.
- **THEN** The line of `criterion_dropped` names a group that changes only test files, names the earlier group that changes the code, and says that such a group is no `criterion_dropped`.

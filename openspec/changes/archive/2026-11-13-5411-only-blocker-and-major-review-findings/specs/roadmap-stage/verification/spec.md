## ADDED Requirements

### Requirement: A finding has a severity
Each finding of a verification reply SHALL have a `severity` that is one of `blocker`, `major`, `minor` and `nit`, the grades of the golden set. A reply with a finding with no severity, or with another severity, SHALL fail the schema. The prompt of the pass SHALL describe the four severities and SHALL say that only a `blocker` or a `major` finding can stop the plan. The comment line of a finding SHALL start with its severity.

#### Scenario: A finding with no severity
- **WHEN** a reply holds a finding with no `severity`, or with the severity `low`
- **THEN** the reply fails the schema

#### Scenario: The prompt names the severities
- **WHEN** the prompt of the pass is read
- **THEN** its line of `severity` names `blocker`, `major`, `minor` and `nit`, the values of the schema, and the prompt says that only a `blocker` or `major` finding can stop the plan

### Requirement: Only a blocker or a major finding is open
Only a finding of the severity `blocker` or `major` SHALL be open (`OPEN_SEVERITIES`). A `minor` or a `nit` finding SHALL be advice: it SHALL return no plan, keep no draft with `plan/needs-fix`, and go into the comment with the points that stop no draft. A later review SHALL open a new finding by the same rule, and an earlier finding SHALL keep its severity.

#### Scenario: A minor finding with a quote
- **WHEN** the verifier returns a `spec_delta_wrong` finding with the severity `minor`, whose quote is in the input and whose place the plan holds
- **THEN** the planner gets no second request, the draft pull request gets no `plan/needs-fix`, and the comment lists the line ``- minor `spec_delta_wrong` at tasks (1): ...`` with the points that stop no draft

#### Scenario: A nit placeholder finding
- **WHEN** the verifier returns a finding with the severity `nit` that reports a placeholder that the plan holds
- **THEN** the finding is advice

#### Scenario: A minor new finding of a later review
- **WHEN** a later review marks the earlier finding `gone` and reports a `minor` finding whose quote is in a block of `answer`
- **THEN** the earlier finding is fixed, and the new finding is advice and no added finding

### Requirement: A spec delta finding needs a scenario with no part that a test can assert
The prompt of the pass SHALL describe a `spec_delta_wrong` scenario defect as a scenario where no test can assert any part of its THEN, and SHALL grade a scenario with one part that no test can assert as `minor` when a test can assert the other parts.

#### Scenario: The prompt of the spec delta type
- **WHEN** the line of `spec_delta_wrong` of the prompt is read
- **THEN** it holds "a scenario where no test can assert any part of its THEN"

## MODIFIED Requirements

### Requirement: An evidence-backed finding returns the plan for the set repair rounds
A finding of the severity `blocker` or `major` and of an open type (`OPEN_TYPES`) that quotes its input or a tool answer of the run, on a place of the plan or the issue, SHALL return the plan to the planner with each open finding of the round as the problem. The revision SHALL pass the gates and the review again, at most `roadmap.stage.verify_repair_rounds` times (two by default), and for each extra round of the extension.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a major `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a major `false_premise` finding whose quote is in none of the issue, the plan, the cited files and the tool answers of the run
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the first revised plan gets a major `missing_path` finding with a quote
- **THEN** the planner gets a second repair request with the finding as `problem`

#### Scenario: A task order finding returns the plan
- **WHEN** the verifier returns a major `task_order` finding whose quote is in the plan
- **THEN** the planner gets a second request with the finding as `problem`

#### Scenario: A quote from a tool answer
- **WHEN** the verifier reads a line past the cap of a cited file with a tool, and returns a major `ignores_existing_code` finding that quotes that line
- **THEN** the planner gets a repair request with the finding as `problem`

#### Scenario: A place that the plan does not hold
- **WHEN** the verifier returns a major `false_premise` finding whose quote is in the issue and whose place is a key that the plan does not have
- **THEN** the planner gets no second request and the finding goes into the comment

### Requirement: Every open finding returns the plan to the planner
Each open finding of a review SHALL return the plan to the planner while a repair round remains, with each open finding of the review in `problem`. An open finding is a finding of the severity `blocker` or `major` (`OPEN_SEVERITIES`) that is a quoted finding of an open type (`OPEN_TYPES`: `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`), or a finding that reports a placeholder that the request holds.

#### Scenario: A quoted dropped criterion finding returns the plan
- **WHEN** the verifier returns a major `criterion_dropped` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem` and the first plan as `previous`, and the staged change holds the revised plan and no open finding

#### Scenario: A quoted spec delta finding returns the plan
- **WHEN** the verifier returns a major `spec_delta_wrong` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

#### Scenario: A placeholder finding returns the plan
- **WHEN** the verifier returns a major finding that reports a placeholder that the issue holds, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

## ADDED Requirements

### Requirement: A finding names its place in the plan or the issue
Each finding of the verification reply SHALL name its place in `where` with a `part` and a `section`. The part SHALL be one of `proposal`, `design`, `tasks`, `spec` and `issue`. The section SHALL be a key or a text of the proposal or the design, the number of a task group, the name of a requirement of the spec delta with its capability in `capability`, or a text of the issue. The comment line of a finding SHALL show the part, the capability when it has one, and the section in brackets.

#### Scenario: A dropped criterion names the criterion of the issue
- **WHEN** the review returns a `criterion_dropped` finding whose part is `issue` and whose section and quote are the text of an acceptance criterion of the issue
- **THEN** `open_findings` returns the finding

#### Scenario: The place in a comment line
- **WHEN** the comment lists a `spec_delta_wrong` finding on the requirement `A release keeps a Status` of `roadmap-item-claim`
- **THEN** its line starts with "- `spec_delta_wrong` at spec roadmap-item-claim (A release keeps a Status): "

### Requirement: A finding on a place that the plan does not hold is advice
A finding whose place the plan or the issue of the request does not hold SHALL be advice, whatever its type and its quote. A text of a tool answer SHALL NOT make a place that the plan holds. In a later review, the rule SHALL apply to each new finding on the revision, and an earlier finding that the review marks `holds` SHALL stay open with its place.

#### Scenario: A finding on a requirement that the plan does not hold
- **WHEN** the review of the plan of pull request #5350 at head ccfbab2e9586, whose spec delta changes three requirements of `roadmap-item-claim`, returns a `spec_delta_wrong` finding on a fourth requirement with a quote from a `read_spec` answer
- **THEN** `open_findings` returns no finding

#### Scenario: A finding on a requirement of the plan
- **WHEN** the review of the same plan returns a `spec_delta_wrong` finding on the requirement `A release keeps a Status that a job did not set` of `roadmap-item-claim` with a quote of the plan
- **THEN** `open_findings` returns the finding

#### Scenario: A group that the plan does not hold
- **WHEN** the review of a plan with two task groups returns a `missing_path` finding on group 3 with a quote of the plan
- **THEN** `open_findings` returns no finding

#### Scenario: A later review opens a finding on a requirement that the revision does not hold
- **WHEN** a later review marks the earlier finding `gone` and opens a `spec_delta_wrong` finding whose quote is in a block of `answer` and whose place is a requirement that the spec delta of the revision does not hold
- **THEN** the finding is advice, the planner gets no third request, and the staged change holds the revision with no open finding

#### Scenario: An earlier finding that holds keeps its place
- **WHEN** a later review marks `holds` an earlier finding on group 2, and the revision has one group
- **THEN** the finding stays open

## MODIFIED Requirements

### Requirement: An evidence-backed finding returns the plan for the set repair rounds
A finding of type `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped` that quotes its input or a tool answer of the run, on a place of the plan or the issue, SHALL return the plan to the planner with each open finding of the round as the problem. The revision SHALL pass the gates and the review again, at most `roadmap.stage.verify_repair_rounds` times (two by default), and for each extra round of the extension.

#### Scenario: A false premise with a quote
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue
- **THEN** the planner gets a second request with the finding as `problem` and the first plan as `previous`, and the job opens the draft pull request with the revised plan

#### Scenario: A quote that is not in the input
- **WHEN** the verifier returns a `false_premise` finding whose quote is in none of the issue, the plan, the cited files and the tool answers of the run
- **THEN** the planner gets no second request and the finding goes into the comment

#### Scenario: The revised plan has a finding too
- **WHEN** the first revised plan gets a `missing_path` finding with a quote
- **THEN** the planner gets a second repair request with the finding as `problem`

#### Scenario: A task order finding returns the plan
- **WHEN** the verifier returns a `task_order` finding whose quote is in the plan
- **THEN** the planner gets a second request with the finding as `problem`

#### Scenario: A quote from a tool answer
- **WHEN** the verifier reads a line past the cap of a cited file with a tool, and returns an `ignores_existing_code` finding that quotes that line
- **THEN** the planner gets a repair request with the finding as `problem`

#### Scenario: A place that the plan does not hold
- **WHEN** the verifier returns a `false_premise` finding whose quote is in the issue and whose place is a key that the plan does not have
- **THEN** the planner gets no second request and the finding goes into the comment

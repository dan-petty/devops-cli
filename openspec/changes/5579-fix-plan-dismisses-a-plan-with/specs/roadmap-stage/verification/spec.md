## MODIFIED Requirements

### Requirement: Only a blocker or a major finding is open
Only a finding of the severity `blocker` or `major` SHALL be open. The type SHALL NOT keep a finding out of the open set, so a major finding of the type `other` SHALL be open. A `minor` or a `nit` finding SHALL be advice: it SHALL return no plan, keep no draft with `plan/needs-fix`, and go into the comment. A later review SHALL open a new finding by the same rule, and an earlier finding SHALL keep its severity.

#### Scenario: A minor finding with a quote
- **WHEN** the verifier returns a finding of the severity `minor`, whose quote is in the input and whose place the plan holds
- **THEN** the planner gets no second request, the draft pull request gets no `plan/needs-fix`, and the comment lists the minor finding with the points that stop no draft

#### Scenario: A nit placeholder finding
- **WHEN** the verifier returns a finding with the severity `nit` that reports a placeholder that the plan holds
- **THEN** the finding is advice

#### Scenario: A minor new finding of a later review
- **WHEN** a later review marks the earlier finding `gone` and reports a `minor` finding whose quote is in a block of `answer`
- **THEN** the earlier finding is fixed, and the new finding is advice and no added finding

#### Scenario: A major finding of type other
- **WHEN** the verifier returns an `other` finding with the severity `major`, whose quote is in the input and whose place the plan holds
- **THEN** the finding is open, it returns the plan to the planner, and the draft pull request keeps `plan/needs-fix`

### Requirement: Every open finding returns the plan to the planner
Each open finding of a review SHALL return the plan to the planner while a repair round remains, with each open finding of the review in `problem`. An open finding is a finding of the severity `blocker` or `major` (`OPEN_SEVERITIES`) that is a quoted finding of an open type (`OPEN_TYPES`), or a finding that reports a placeholder that the request holds. `OPEN_TYPES` SHALL hold the nine types that `VERIFY_TYPES` names, so the severity alone decides whether a finding returns the plan.

#### Scenario: A quoted dropped criterion finding returns the plan
- **WHEN** the verifier returns a major `criterion_dropped` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem` and the first plan as `previous`, and the staged change holds the revised plan and no open finding

#### Scenario: A quoted spec delta finding returns the plan
- **WHEN** the verifier returns a major `spec_delta_wrong` finding whose quote is in the issue, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

#### Scenario: A placeholder finding returns the plan
- **WHEN** the verifier returns a major finding that reports a placeholder that the issue holds, and the review of the revised plan finds nothing
- **THEN** the planner gets a second request with the finding in `problem`, and the staged change holds no open finding

#### Scenario: An other finding with a quote returns the plan
- **WHEN** the verifier returns an `other` finding of severity `major` whose quote is in the input
- **THEN** the finding is open, and returns the plan to the planner

### Requirement: Other findings go into the comment
The job SHALL list each finding that does not return the plan in the comment that names the draft pull request, with its type, place, problem and quote. The text of a finding SHALL be on one line, with a handle, a link or a reference to another repository in a code span. The job SHALL open the draft pull request.

#### Scenario: A contrived test finding
- **WHEN** the verifier returns a minor `contrived_test` finding
- **THEN** the comment lists the finding and the draft pull request is open

#### Scenario: No finding
- **WHEN** the verifier returns no finding
- **THEN** the comment holds no findings section

### Requirement: The comment lists every finding of each repair round
After the last repair round, the plan SHALL keep each open finding of the last review, and the comment SHALL list every finding of each round.

#### Scenario: The second repair round still has a finding
- **WHEN** the plan still has a return finding after the second repair round
- **THEN** the planner makes no further request, the job keeps the draft with the label `plan/needs-fix`, and the issue receives a comment with the findings

#### Scenario: The comment lists each repair round
- **WHEN** the verifier returns a return finding on each of the first two reviews, and no finding on the third
- **THEN** the planner makes two repair requests, and the comment of the item lists the two return findings

#### Scenario: A mixed first round
- **WHEN** the first review returns a `false_premise`, a `spec_delta_wrong` and a major `contrived_test` finding with quotes, and the second review finds nothing
- **THEN** the planner gets all three findings in `problem`, the comment lists all three, and no finding is open

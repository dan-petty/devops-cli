## ADDED Requirements

### Requirement: A plan comment line that the step cannot read keeps the label
The step SHALL count each line of the open findings section of the last plan comment that matches neither line form. When that count is above zero, the step SHALL end the attempt with the result `unreadable_findings` before any model call, SHALL keep `plan/needs-fix`, and SHALL write no `dismissed`, `cleared` or `revised` result. The result line SHALL hold `unreadable` with that count, and the step SHALL log one line for each line that it could not read.

#### Scenario: Two lines that neither form matches
- **WHEN** the open findings section of the last plan comment holds two lines that match neither form
- **THEN** the result is `unreadable_findings`, the pull request keeps `plan/needs-fix`, and the result line holds `unreadable` with the count 2

#### Scenario: An unreadable line starts no model call
- **WHEN** the open findings section of the last plan comment holds a line that matches neither form
- **THEN** the step makes no plan call and no review call, and the record counts the attempt on the head

### Requirement: An open finding of the last plan comment keeps the label
The step SHALL dismiss a plan only when the review of the head and the last plan comment list no blocker or major finding. A blocker or a major finding of the comment SHALL keep `plan/needs-fix`, and the attempt SHALL be `unchanged`.

#### Scenario: An old-form comment keeps the label
- **WHEN** the last plan comment holds a finding line of the old form, and the review of the head has no open finding
- **THEN** the result is `unchanged`, and the pull request keeps `plan/needs-fix`

#### Scenario: A comment with no open finding is dismissed
- **WHEN** the last plan comment lists no blocker or major finding, and the review of the head has no open finding
- **THEN** the result is `dismissed`, and the pull request loses `plan/needs-fix`

## MODIFIED Requirements

### Requirement: A plan comment line is read in either of its forms
The step SHALL read a finding line of a plan comment in the current form and in the form that a release before #5418 wrote. A line with no severity SHALL read as a major finding. An old place SHALL give the part of its finding from its first word, and the whole old place SHALL be the section of that part. The finding of an old line SHALL name no capability.

#### Scenario: An old-form line reads as a finding
- **WHEN** a plan comment holds a finding line with no severity, whose type is `other` and whose place is `group 3 (and group 1)`
- **THEN** the step reads one finding with the type `other`, the severity `major`, the part `tasks` and the section `group 3 (and group 1)`

#### Scenario: A current-form line keeps its severity
- **WHEN** the stage job wrote a blocker finding in the current form
- **THEN** the step reads the finding with the severity `blocker`, its part, its capability and its section

#### Scenario: A real stage comment of the old form
- **WHEN** the step reads the open findings of a real stage comment whose lines have no severity
- **THEN** it reads the finding as a major finding

#### Scenario: A line with a severity
- **WHEN** the step reads a comment that the stage job wrote for a blocker finding
- **THEN** it reads the finding back with the severity `blocker`

### Requirement: The decisions of the step count only blocker and major findings
The step SHALL count only a blocker or a major finding as open. A head whose review has only minor or nit findings SHALL be `dismissed` when the last plan comment lists no blocker or major finding. A pushed revision and a plan that loses the label SHALL list the other findings of its reviews as advice. A failed or a worse revision SHALL list none.

#### Scenario: A head with only a minor finding
- **WHEN** the last plan comment lists no blocker or major finding, and the review of the head has only a quoted finding with the severity `minor`
- **THEN** the planner gets no request, the head of the branch does not change, the result is `dismissed` with `before` 0, the pull request loses `plan/needs-fix`, and the comment lists the minor finding as advice

#### Scenario: A minor finding of the comment is advice
- **WHEN** the last plan comment lists a minor finding, and the review of the head has no open finding
- **THEN** the result is `dismissed`, and the pull request loses `plan/needs-fix`

#### Scenario: A pushed revision lists its minor finding as advice
- **WHEN** the step pushes a revision whose review holds a quoted minor finding and no blocker or major finding
- **THEN** the pull request loses `plan/needs-fix`, and the comment lists the minor finding as advice

## RENAMED Requirements

- FROM: `### Requirement: A comment line with no severity reads as a major finding`
- TO: `### Requirement: A plan comment line is read in either of its forms`

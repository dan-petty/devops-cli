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
The step SHALL dismiss a plan only when the review of the head and the last plan comment list no blocker or major finding. A head with no open findings in its review, but whose last plan comment lists a blocker or a major finding, SHALL NOT be dismissed, SHALL keep `plan/needs-fix`, and the attempt SHALL be `unchanged`.

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

### Requirement: The review of the head counts the open findings before the repair
In each attempt the verification pass SHALL review the plan that passed the checks at the latest default branch, with no screen of `stage.verify_screen`, and the step SHALL compare the last review of the revision with the open findings of that review. The step SHALL give the planner the open findings of that review and the open findings of the last trusted comment of the stage job or of the step that names the pull request. When the review of the head plan has no open finding but the comment lists an open finding, the step SHALL NOT dismiss the plan, SHALL keep `plan/needs-fix`, and SHALL report `unchanged`.

#### Scenario: No comment lists an open finding
- **WHEN** no trusted comment of the item lists an open finding for the pull request, and the review of the head plan has one
- **THEN** the next planner request holds the head plan as `previous` and the finding of the review in `problem`

#### Scenario: A comment of an untrusted author
- **WHEN** the only comment that lists an open finding has an author with no write access, and the review of the head plan has an open finding
- **THEN** the next planner request holds the finding of the review in `problem` and no finding of that comment

#### Scenario: The comment lists fewer open findings than the review of the head
- **WHEN** the stage comment lists 1 open finding, the review of the head plan has 2 and the last review of the revision has 1
- **THEN** the step pushes the revision with the result `revised`, and its result line holds `comment=1`, `before=2` and `after=1`

#### Scenario: The review of the head finds no open finding that the comment lists
- **WHEN** the stage comment lists an open finding and the review of the head plan has none
- **THEN** the planner gets no request, the head of the branch does not change, the pull request keeps `plan/needs-fix`, and the result is `unchanged`

#### Scenario: The screen does not decide the review of the head
- **WHEN** the screen of `stage.verify_screen` is in mode `on` and gives the band `continue`
- **THEN** the verification pass reviews the plan of the head, and its open findings are `before`

### Requirement: The label goes when no open finding remains
The step SHALL remove `plan/needs-fix` for the result `cleared` (a pushed revision whose last review has no open finding), for `dismissed` (a review of the head with no open finding and no open finding listed in the last plan comment), and for `regated` only when the review of the gated plan has no open finding and no step failed. It SHALL keep the label for each other result.

#### Scenario: A revision with no open finding
- **WHEN** the review of the head has an open finding and the review of the revision has none
- **THEN** the branch holds the new commit, the result is `cleared`, and the pull request loses `plan/needs-fix`

#### Scenario: A head plan with no open finding
- **WHEN** the checks pass the plan of the head, the review of it has no open finding, and the last plan comment lists no open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request loses `plan/needs-fix`, the result is `dismissed`, and the comment lists the findings as advice

## RENAMED Requirements

- FROM: `### Requirement: A comment line with no severity reads as a major finding`
- TO: `### Requirement: A plan comment line is read in either of its forms`

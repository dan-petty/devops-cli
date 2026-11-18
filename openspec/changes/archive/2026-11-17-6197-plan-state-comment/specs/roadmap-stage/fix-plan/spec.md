## MODIFIED Requirements

### Requirement: The label goes when no open finding remains
The step SHALL remove `verdict/fix-plan` for the result `cleared` (a pushed revision whose last review has no open finding), for `dismissed` (a review of the head with no open finding and no open finding listed in the last plan comment), and for `regated` only when the review of the gated plan has no open finding and no step failed. It SHALL keep the label for each other result.

#### Scenario: A revision with no open finding
- **WHEN** the review of the head has an open finding and the review of the revision has none
- **THEN** the branch holds the new commit, the result is `cleared`, and the pull request loses `verdict/fix-plan`

#### Scenario: A head plan with no open finding
- **WHEN** the checks pass the plan of the head, the review of it has no open finding, and the last plan comment lists no open finding
- **THEN** the planner gets no request, the head of the branch does not change, the pull request loses `verdict/fix-plan`, the result is `dismissed`, and the plan-state comment lists the findings as advice

### Requirement: The decisions of the step count only blocker and major findings
The step SHALL count only a blocker or a major finding as open. A head whose review has only minor or nit findings SHALL be `dismissed` when the last plan comment lists no blocker or major finding. A pushed revision and a plan that loses the label SHALL give the other findings of its reviews as the advice of the plan-state comment. A failed or a worse revision SHALL give none.

#### Scenario: A head with only a minor finding
- **WHEN** the last plan comment lists no blocker or major finding, and the review of the head has only a quoted finding with the severity `minor`
- **THEN** the planner gets no request, the head of the branch does not change, the result is `dismissed` with `before` 0, the pull request loses `verdict/fix-plan`, and the plan-state comment lists the minor finding as advice

#### Scenario: A minor finding of the comment is advice
- **WHEN** the last plan comment lists a minor finding, and the review of the head has no open finding
- **THEN** the result is `dismissed`, and the pull request loses `verdict/fix-plan`

#### Scenario: A pushed revision lists its minor finding as advice
- **WHEN** the step pushes a revision whose review holds a quoted minor finding and no blocker or major finding
- **THEN** the pull request loses `verdict/fix-plan`, and the plan-state comment lists the minor finding as advice

### Requirement: An attempt that ends at the budget comments and logs its result
An attempt that ends `timeout` SHALL post one comment with the marker `<!-- devops roadmap fix-plan -->` on the issue. The comment SHALL name the budget, the step in which it ended and the counts of the attempt, and SHALL list no open finding: the plan-state comment of the pull request SHALL list the open findings that keep the label. The result line SHALL hold `result=timeout`, `success=false`, `class=timeout` and the step.

#### Scenario: The comment and the result line of a timeout
- **WHEN** the budget of 600 seconds ends after the review of the head found one open finding
- **THEN** the comment names 600 seconds and lists no open finding, the state comment lists the open finding, and the result line holds `result=timeout`, `class=timeout`, `step=plan` and `before=1` and no `after`

## ADDED Requirements

### Requirement: The last plan comment is the plan-state comment of the pull request
The last plan comment of a plan pull request SHALL be its plan-state comment, the first trusted comment of the item that holds its key. For a pull request with no state comment, it SHALL be the newest trusted legacy comment of the stage job or of the step that names the pull request, and the comment of a run SHALL NOT be one.

#### Scenario: The state comment holds and a newer comment of a run does not
- **WHEN** the item holds the state comment of the pull request with one open finding, and a newer comment of an attempt that lists none
- **THEN** the last plan comment is the state comment, and its open finding is read

#### Scenario: A pull request staged before the state comment
- **WHEN** the item holds a legacy stage comment with an open finding, and a newer comment of a run for the pull request
- **THEN** the last plan comment is the legacy stage comment

### Requirement: An attempt that comments writes the plan-state comment first
An attempt that posts a comment SHALL first write the state comment: an edit of the comment that holds the key, else a new comment. It SHALL list the open findings that keep the label and the advice. A pushed plan SHALL give the groups; else the groups of the last plan comment, or of the newest legacy stage comment, SHALL stay. The comment of the attempt SHALL hold an event line and the facts of the attempt, and no finding and no advice: it SHALL say that the state comment lists them.

#### Scenario: A pushed revision edits the state comment
- **WHEN** the state comment lists one open finding, and the attempt pushes a revision that keeps 1 of 2 open findings of the head
- **THEN** the item holds the state comment, edited, with that finding and the groups of the pushed plan, and one comment of the attempt with the counts and no open finding

#### Scenario: A timeout on a pull request staged before the state comment
- **WHEN** the item holds only a legacy stage comment with groups and advice, and the budget ends after the review of the head
- **THEN** the step posts a state comment with the groups and the advice of the legacy comment and the open finding of the review, and the legacy comment stays

#### Scenario: No line of the comment of an attempt is in the state comment
- **WHEN** an attempt pushes a revision whose review holds a minor finding, or dismisses a head whose review holds one
- **THEN** the state comment lists the minor finding as advice, no line of text of the comment of the attempt is in the state comment, and the comment of the attempt says that the state comment lists the advice

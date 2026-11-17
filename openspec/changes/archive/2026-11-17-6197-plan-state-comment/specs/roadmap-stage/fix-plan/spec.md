## MODIFIED Requirements

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
An attempt that posts a comment SHALL first write the state comment: an edit of the comment that holds the key, else a new comment. The state comment SHALL list the open findings that keep the label and the advice. A pushed plan SHALL give the task groups. With no push, the groups of the last plan comment SHALL stay, or those of the newest legacy stage comment. The comment of the attempt SHALL hold a hidden event line, the facts of the attempt and no list of open findings.

#### Scenario: A pushed revision edits the state comment
- **WHEN** the state comment lists one open finding, and the attempt pushes a revision that keeps 1 of 2 open findings of the head
- **THEN** the item holds the state comment, edited, with that finding and the groups of the pushed plan, and one comment of the attempt with the counts and no open finding

#### Scenario: A timeout on a pull request staged before the state comment
- **WHEN** the item holds only a legacy stage comment with groups and advice, and the budget ends after the review of the head
- **THEN** the step posts a state comment with the groups and the advice of the legacy comment and the open finding of the review, and the legacy comment stays

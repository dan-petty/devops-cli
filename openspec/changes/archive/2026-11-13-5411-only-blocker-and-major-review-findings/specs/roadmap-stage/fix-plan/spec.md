## ADDED Requirements

### Requirement: The decisions of the step count only blocker and major findings
The step SHALL take `before`, the fixed and added findings of a revision and the open findings of its last review from the open findings of the verification pass, so only a blocker or a major finding counts. A head whose review has only minor or nit findings SHALL be `dismissed` when no other rule applies. The comment of a pushed revision, or of a plan that loses the label, SHALL list the other findings of its reviews as advice. A failed or a worse revision SHALL list none.

#### Scenario: A head with only a minor finding
- **WHEN** the last plan comment lists an open finding, and the review of the head has only a quoted `spec_delta_wrong` finding with the severity `minor`
- **THEN** the planner gets no request, the head of the branch does not change, the result is `dismissed` with `before` 0, the pull request loses `plan/needs-fix`, and the comment lists the finding of the plan comment as dismissed and the minor finding as advice

### Requirement: A comment line with no severity reads as a major finding
The step SHALL read the severity at the start of a finding line of a plan comment. A line with no severity, which a release before #5411 wrote, SHALL read as a major finding, because each open finding of that release kept the draft.

#### Scenario: A real stage comment of the old form
- **WHEN** the step reads the open findings of a real stage comment whose lines have no severity
- **THEN** it reads the finding as a major finding

#### Scenario: A line with a severity
- **WHEN** the step reads a comment that the stage job wrote for a blocker finding
- **THEN** it reads the finding back with the severity `blocker`

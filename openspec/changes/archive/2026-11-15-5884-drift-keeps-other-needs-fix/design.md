# Design

## Decisions

- The drift comment holds the claim of the row. The row already keeps one marked comment for each plan, so a hidden line in that comment costs no new label and no new store. A comment with the marker and no claim line has the claim `added`. The line `<!-- devops roadmap plan drift: label held -->` gives `held`, and `<!-- devops roadmap plan drift: cleared -->` gives `cleared`.
- At a round with problems, the claim is `added` when the label is absent or the comment already has the claim `added`. Else another check holds the label, and the claim is `held`. The row adds the label in both cases, so a label that a person removed comes back while the plan has problems.
- At a passing round, an open claim (`added` or `held`) changes to `cleared`, so a later label of another check is safe from the row. The row removes the label only for the claim `added`.
- The row also keeps the label while the last plan comment of the item lists an open finding (`plan_comment`, `comment_open_findings`). The step fix-plan works on each plan with the label, the drift plan too, and it can keep the label for an open finding of its own review after the row added it. A line of that section that does not read as a finding keeps the label.

## Rejected alternatives

- A separate label, such as `plan/drift`. `stage_ready`, the implement job, `phase.py`, `implement_submit.py`, `failure.py` and the step fix-plan all read `plan/needs-fix`. Each would need a change, and the step fix-plan would stop repairing a drifted plan. The comment claim needs a change only in `plan_drift.py`.
- The drift comment alone, with no claim line: remove the label when an open drift comment exists. This removes a label that the stage review added before the drift, and a label that the step fix-plan kept after it.
- The head commit at the time of the label: remove the label only while the head is the same. A person who pushes a fix for the drift would leave the label until the step fix-plan clears it hours later.

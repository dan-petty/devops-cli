# Design

## Decisions

- **One function measures the body, and each check calls it.**: `open_body_problems`, `body_problems`, `plan_body_problems` and the plan check give the limit the text of `measured_body_text`. Two copies of the measure disagreed on a body that starts with a blank line, and one function cannot disagree with itself.
- **Split `body.strip()`.**: `body_problems`, `plan_body_problems` and `_closing_problems` already read the lines of `body.strip()`, and git removes the blank lines at the start of a commit message. The squash message thus has no leading blank line to count.
- **End the text at the first line that is `Closes #<issue>` or `Plans #<issue>` when the whitespace at its ends is removed.**: `_CLOSES_LINE` and `_PLANS_LINE` take the line after `str.strip()`. That is the rule of `plan_check.issue_number`, which takes a `Plans` line with a space at its end as the plan of the issue. If the measure does not end the text at that line, the plan check reports a false `body-length` problem. The old `startswith` match ends the text at a line such as `Closes #abc` that no check takes as the line.

- **One predicate takes the marker line for each reader.**: `marker_issue` strips the line, then matches the whole line. `measured_body_text`, `_closing_problems`, `plan_body_problems`, `plan_check.issue_number` and `grounding.plan_blockers` call it. When the measure and the form check used two rules, a padded `Plans` line above the exact line ended the measured text, but the form check counted one `Plans` line. The text between the two lines then passed the limit unmeasured.
- **The issue of a marker line has ASCII digits only.**: GitHub links `#` with ASCII digits only. The plan check already took only `[0-9]`, and the form check and the grounding took any Unicode digit with `\d`. One predicate needs one digit class, and the class of GitHub does not let the plan check take more lines.

## Rejected alternatives

- **Split `body.strip()` only in `measured_body_text`, and keep the text of `lines[:closes_at]` in `body_problems`.**: It fixes the leading blank line, but it keeps two measures that a later change can make disagree again. A body with a `Closes #abc` line above `Closes #5020` still gets two texts.
- **Make the open step split the raw body like the old `measured_body_text`, and change the ready check to it.**: A leading blank line then counts in the limit, but the squash message does not keep it, so the limit counts a character that `git log` does not show.
- **Match the exact line in `measured_body_text`, with no `str.strip()`.**: The form check takes only the exact line, but the plan check takes a line with whitespace at its ends. The text then ends at no line in a body that the plan check accepts, and the plan check measures the `Plans` line and the lines below it.
- **Let the plan check use `_PLANS_LINE` of `pull_form` with `\d`.**: `\d` takes any Unicode digit, such as `\u0661`, and the plan check takes only `[0-9]`. The plan check would take more lines as the plan of an issue than now.
- **Report a second padded `Plans` line in `plan_body_problems` only.**: It closes the gap of the measure, but the form check, the plan check and the grounding keep three rules that a later change can make disagree again.

# Design

## Decisions

- **One function measures the body, and each check calls it.**: `open_body_problems`, `body_problems`, `plan_body_problems` and the plan check give the limit the text of `measured_body_text`. Two copies of the measure disagreed on a body that starts with a blank line, and one function cannot disagree with itself.
- **Split `body.strip()`.**: `body_problems`, `plan_body_problems` and `_closing_problems` already read the lines of `body.strip()`, and git removes the blank lines at the start of a commit message. The squash message thus has no leading blank line to count.
- **End the text at the first line that is `Closes #<issue>` or `Plans #<issue>` when the whitespace at its ends is removed.**: `_CLOSES_LINE` and `_PLANS_LINE` take the line after `str.strip()`. That is the rule of `plan_check.issue_number`, which takes a `Plans` line with a space at its end as the plan of the issue. If the measure does not end the text at that line, the plan check reports a false `body-length` problem. The old `startswith` match ends the text at a line such as `Closes #abc` that no check takes as the line.

## Rejected alternatives

- **Split `body.strip()` only in `measured_body_text`, and keep the text of `lines[:closes_at]` in `body_problems`.**: It fixes the leading blank line, but it keeps two measures that a later change can make disagree again. A body with a `Closes #abc` line above `Closes #5020` still gets two texts.
- **Make the open step split the raw body like the old `measured_body_text`, and change the ready check to it.**: A leading blank line then counts in the limit, but the squash message does not keep it, so the limit counts a character that `git log` does not show.
- **Match the exact line in `measured_body_text`, with no `str.strip()`.**: The form check takes only the exact line, but the plan check takes a line with whitespace at its ends. The text then ends at no line in a body that the plan check accepts, and the plan check measures the `Plans` line and the lines below it.
- **Let the plan check use `_PLANS_LINE` of `pull_form`.**: `_PLANS_LINE` takes any Unicode digit with `\d`, such as `\u0661`, and the plan check takes only `[0-9]`. The plan check would take more lines as the plan of an issue than now.

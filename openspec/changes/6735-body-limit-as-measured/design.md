# Design

## Decisions

- **One function measures the body, and each check calls it.**: `open_body_problems`, `body_problems`, `plan_body_problems` and the plan check give the limit the text of `measured_body_text`. Two copies of the measure disagreed on a body that starts with a blank line, and one function cannot disagree with itself.
- **Split `body.strip()`.**: `body_problems`, `plan_body_problems` and `_closing_problems` already read the lines of `body.strip()`, and git removes the blank lines at the start of a commit message. The squash message thus has no leading blank line to count.
- **End the text at the line that the form takes as `Closes` or `Plans`.**: `_CLOSES_LINE` and `_PLANS_LINE` find the line that the form check uses. The old `startswith` match is a second meaning of the line, and it ends the text at a line such as `Closes #abc` that the form does not take.

## Rejected alternatives

- **Split `body.strip()` only in `measured_body_text`, and keep the text of `lines[:closes_at]` in `body_problems`.**: It fixes the leading blank line, but it keeps two measures that a later change can make disagree again. A body with a `Closes #abc` line above `Closes #5020` still gets two texts.
- **Make the open step split the raw body like the old `measured_body_text`, and change the ready check to it.**: A leading blank line then counts in the limit, but the squash message does not keep it, so the limit counts a character that `git log` does not show.

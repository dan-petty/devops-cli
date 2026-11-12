# Design

## Decisions

- The review result list keeps its `ReviewResult | str` items and only loses the persona. A review returns one result, and the raw-reply branch of the comment formatter stays as it is, so the change stays small.
- The model notes of more than one result go under one `Model Notes (Not Verified)` heading, separated by a blank line. With no persona there is no subheading to give each one.
- The routed-file messages get new names, `secret_scan_only` and `secret_scan_only_unscanned`, because the old names describe the personas.
- The persona text of other review modules (`pipeline.py`, `profile.py`, `panels.py` and the finding panel of `commands/review.py`) stays for a later change. The issue lists only the files that this change fixes.

## Rejected alternatives

- Return one `ReviewResult` in place of a list: rejected for this change. Every caller and many tests read a list, so the change would grow past the scope of the issue.
- Keep a neutral label such as `Review` in place of the persona title: rejected. The comment already has the `AI Code Review` heading, so a second label adds nothing.

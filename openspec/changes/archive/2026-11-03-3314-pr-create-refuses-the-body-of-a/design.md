# Design

## Decisions

- **Read a plan by its title with `plan_issue`, as readiness does.**: One function states what a plan title is, so `pr create` and `check-readiness` agree.
- **Add `plan_body_problems` beside `body_problems` in `src/devops_cli/roadmap/pull_form.py` and reuse `_change_problems`, `_text_problems` and `_trailer_problems`.**: The text, length and trailer bounds of a plan body are those of a delivery body, so only the `Plans` line and the closing rule differ.
- **Refuse any closing reference in a plan body with `_CLOSING_REFERENCE`.**: The pattern already finds `Closes`, `Fixes` and `Resolves` with an issue reference, and it matches what GitHub closes.

## Rejected alternatives

- **Add a flag to `pr create` that skips the form check.**: A flag lets any pull request skip the form, and the title already says that a pull request is a plan.
- **Send the body with `devops gh api`.**: `uv run devops gh api --help` lists no option for a request body.
- **Call `plan_blockers` of `grounding.py` for the body.**: It needs the changed files, and `pr create` runs before the pull request exists.

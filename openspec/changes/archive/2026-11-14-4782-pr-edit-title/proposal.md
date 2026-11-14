# Proposal

## Why

`devops pr create` refuses a title that breaks the form with `title_problems`, and agent title failures fell from 41 to 2 after that check (#3213). `devops pr edit --title` has no check, so an edit can set a title that the `PR Title` check refuses (#4782).

## What Changes

- `edit_pr` runs `title_problems` on a given `--title`, and refuses it with the message of `create` before it sends the edit.
- A test refuses a title with `!` and a title with a 70-character summary.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: `devops pr edit` refuses a title that the title check refuses.

## Impact

- Code: `src/devops_cli/commands/pr.py`
- Tests: `tests/commands/test_pr_update.py`

## Feasibility

- `title_problems` already covers the type, the scope, the `!` rule and the summary length.
- The edit path already has the title in hand.
- Verification commands: `uv run devops ci test tests/commands/test_pr_update.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The repository's `title_problems` covers the rules. conventional-pre-commit and commitizen accepted a `!` and a 68-character summary (#4771), so no other tool covers them.

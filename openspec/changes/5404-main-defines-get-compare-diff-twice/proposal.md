# Proposal

## Why

Closes #5404. PR #5387 and PR #5401 merged two minutes apart, and each added `GitHubClient.get_compare_diff` to `src/devops_cli/github/client.py`. Git merged both with no conflict, so the class defines the method twice. ruff F811 and mypy `no-redef` fail, the Static Analysis check of `main` fails, and the pre-push hook refuses every branch that holds this `main`.

## What Changes

- Remove the first definition of `get_compare_diff`. The two bodies are the same.
- Keep one method, with a docstring that names both callers: the review of a pull request (#5346) and the plan diff and release files (#5388).
- Carry no spec delta: no command, option, message or answer changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/github/client.py`, 8 lines removed, one docstring line changed.

## Feasibility

- `git show origin/main:src/devops_cli/github/client.py` holds `def get_compare_diff` at lines 519 and 527 with the same body.
- `uv run devops ci --check --only lint,typecheck` on `main` fails with F811 and `no-redef`, and passes on this branch.

## Existing Tool Considered

ruff and mypy found the defect. No new tool. Cost: about 20,000 tokens, 15 minutes elapsed.

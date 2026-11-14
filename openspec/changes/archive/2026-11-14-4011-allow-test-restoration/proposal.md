# Proposal

## Why

An extra repair turn for a failed `fail-to-pass` check may change only the test files. When the agent restores a source file that the step changed to its content at `keeper.base`, `_foreign_change` compares the checkout only with the tree taken at the start of the turn, so it reports the restoration as a foreign change and stops the step (#4011).

## What Changes

- `_foreign_change` compares each path outside the allowed set with `keeper.base` too. A path whose staged content equals its content at `base` is allowed.
- A real edit and a deletion of a file that exists at `base` still stop the step.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step/exit-checks`: The extra turn accepts a file restored to its base content.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_step.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_step_repair.py`

## Feasibility

- `_extra_turn` already holds `keeper.base`.
- `git diff --cached --quiet <base> -- <path>` answers whether the staged content equals the base content, for an edit and a deletion.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_step_repair.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

git compares the content, and the repository already runs it. No library.

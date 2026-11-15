# Proposal

## Why

The merge-readiness rule of a plan accepted only a pull request that added a file to the active change folder. A correction of a merged plan changes a file and adds none, so `devops pr ready` blocked it although plan-check passed (#5315).

## What Changes

- Accept the statuses `added`, `modified`, `renamed`, `copied` and `changed` of a file in `openspec/changes/<issue>-<slug>/`; a removal alone is still no plan.
- Rename `_adds_to_active_folder` to `_changes_the_active_folder` and correct the message.
- Add the correction case and the removal case in `tests/roadmap/test_grounding.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-grounding`: a plan correction passes the file rule.

## Impact

- Code: `src/devops_cli/roadmap/grounding.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_grounding.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/roadmap/grounding.py:379:def _adds_to_active_folder(` reads only `CONST_PR_FILE_ADDED_STATUSES`.
- Pull request #5310 changes only `openspec/changes/3785-.../proposal.md` with status `modified`.
- `uv run pytest tests/roadmap/test_grounding.py` passes after the change.

## Existing Tool Considered

The rule is in one function. The change widens one set: about 300 tokens to build and 20 a quarter to keep.

## Dependencies

None.

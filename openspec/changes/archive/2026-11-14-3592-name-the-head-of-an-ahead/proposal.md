# Proposal: #3592

## Why

The stage job moves its clone to the staged commit with `git merge --ff-only` (`_move_clone`, #3301). Git reports a clone that is ahead of the staged commit as up to date and keeps its HEAD. The job compares HEAD with the staged commit and stops, so no plan reads a commit it did not name, but the message names only the staged commit. A person cannot tell which local commit the clone kept, and no test pins the check. Closes #3592.

## What Changes

- `_move_clone` reads the short hash and the subject of the clone's HEAD when the merge leaves HEAD at another commit, and the `stage_clone_ahead` message names them with the staged commit.
- A new test moves a clone that is ahead and a clone that is behind, and pins the message and the reached commit.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/round`: The stop of an ahead clone names the commit that the clone kept.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage.py` (new)

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- The check exists and names only the staged commit: `src/devops_cli/roadmap/stage/stage.py:3131:_git(checkout, "merge", "--ff-only", "-q", sha)` and `:3132:if _git(checkout, "rev-parse", "HEAD") != sha`.
- The message holds one field: `src/devops_cli/lang/en/messages.py:4082:stage_clone_ahead`.
- No test names `_move_clone`: `tests/roadmap/stage/` holds `test_roadmap_stage_tools.py` and no module of `stage.py`.
- The new tests pass on the branch: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage.py`.

## Existing Tool Considered

Git's own plumbing covers the move and the read: `git merge --ff-only`, `git rev-parse` and `git log -1`. Git has no mode that refuses a clone that is ahead, so the job keeps its check and adds the two reads to its message. The change is about 8 lines of code and 30 lines of tests.

# Proposal

## Why

`devops roadmap plan-check` fetched `refs/pull/<number>/head` and then read `FETCH_HEAD`, which all worktrees of a checkout share. A fetch by another agent between the two commands made the check read another commit and report a false problem, such as "The head holds no change folder" (#5255).

## What Changes

- `plan_check` fetches the head commit that the pull request names (`facts.head_sha`) and reads that commit, in place of `FETCH_HEAD`.
- Add `test_a_moved_pull_ref_does_not_change_the_tree`: the pull ref moves to another commit, and the check still reads the tree of the named head.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: the check reads the head commit that the pull request names.

## Impact

- Code: `src/devops_cli/roadmap/plan_check.py`
- Tests: `tests/roadmap/test_roadmap_plan_check.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/roadmap/plan_check.py:606` fetches the ref and `:607` reads `FETCH_HEAD`; `facts.head_sha` holds the head.
- A fetch of a reachable commit by its SHA works on GitHub and on the local origin of the tests.
- `uv run pytest tests/roadmap/test_roadmap_plan_check.py` passes after the change.

## Existing Tool Considered

Git takes a commit id in `git fetch`, and the facts already hold it. No tool. The change is two lines: about 300 tokens to build and 20 a quarter to keep.

## Dependencies

None.

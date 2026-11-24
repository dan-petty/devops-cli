# Proposal: #6354

## Why
On 2026-11-18 a run of `devops repos worktrees add` on a clone left the clone in detached HEAD.
The add paths in `src/devops_cli/git/worktree_add.py` and the reclaim path do not change the main worktree HEAD.
When an unforeseen condition leaves HEAD detached after a successful run, the clone loses its active branch.
Closes #6354.

## What Changes
- Add a postcondition context manager in `src/devops_cli/git/worktree_add.py` that reads the original branch of the clone before operations start and restores the original branch if detached.
- Wrap `reclaim_merged_worktrees` and `add_worktree` with the postcondition guard.
- Raise `GitOperationError` naming the branch when restoring the branch fails.
- Add offline regression tests covering create, take-over, reclaim, and restore failure paths.
- This change alters command postcondition behavior, so it carries a spec delta for `repos-worktrees-add`.

This change fits one pull request.

## Capabilities
- Postcondition branch preservation for `devops repos worktrees add` and worktree reclaim.

## Impact
- Ensures that `devops repos worktrees add` leaves the clone on its original branch.
- No breaking changes.

## Feasibility
- Verified against `git symbolic-ref --short -q HEAD` and `git checkout <branch>`.
- Verified that `_create` and `_take_over` do not detach HEAD, and the postcondition guard restores HEAD if detached during operations.

## Existing Tool Considered
- Native Git commands `git symbolic-ref --short -q HEAD` and `git checkout <branch>`.
- No new third-party dependency is required. Deletes zero internal files.

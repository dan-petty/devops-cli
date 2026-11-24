# Design

## Decisions
- Read the original branch with `git symbolic-ref --short -q HEAD` before changing worktrees.
- Restore the original branch in a context manager exit hook if HEAD is detached or changed.
- Wrap both `reclaim_merged_worktrees` and `add_worktree` with the context manager.
- Raise `GitOperationError` naming the target branch when checkout fails.
- Test offline with temporary clones and local bare repositories as origin.

## Rejected alternatives
- Restore inside `add_worktree` only: rejected because `reclaim_merged_worktrees` runs before `add_worktree` and could detach HEAD.
- Do not restore and only log: rejected because callers expect the clone to remain on its branch.

# Design

## Decisions

- **Check the message of git, not the return code.** `git worktree remove` of a worktree that is gone fails with return code 128, the same class of failure as a real refusal. The one thing that separates the two is the message, `is not a working tree`. So the removal in `prune_worktrees` is `removed` when git returned 0 or said that, and `failed` otherwise.
- **Keep the size of the worktree.** The size walk runs before the removal, and it tolerates a file that is gone (it contributes 0). So the `size_bytes` of a worktree that a run in parallel removed is the size it had when the run measured it, which is the honest number and the same a normal removal reports.
- **Report it as `removed`.** `reclaim_merged_worktrees` keeps `removed` and `reclaim_error` separate: `reclaim_error` is built only from `failed` items. Counting the worktree as `removed` is therefore enough to clear the warning, and it needs no change in `worktree_add.py`.
- **The token is a constant.** The message of git is read from its error stream. The constant `CONST_GIT_NOT_A_WORKTREE_TOKEN` names it beside the other git message tokens, so a change in the message of git is found in one place.

## Rejected alternatives

- **Treat return code 128 as `removed`.** 128 is the code of every git failure, not of this one. It would turn a real refusal, such as a locked worktree, into a `removed` and hide the failure.
- **A lock file per worktree.** The two runs already share the repository and the directory. A lock adds a file, a write and a race of its own, and a run that crashes leaves it behind. The message check needs no new state.
- **`git worktree remove --force` for every removal.** It fails on a worktree that is gone as well, so it does not change the message, and it removes a locked or dirty worktree that the run meant to keep.
- **Catch the failure in `reclaim_merged_worktrees` and retry.** The worktree is already gone. There is nothing to retry, and the second run is the one that is correct to say it was removed.

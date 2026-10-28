# Proposal

## Why

Issue #2408: `devops repos worktrees add` says the merged worktrees were not reclaimed when a run in parallel already removed a merged worktree.

- `add` reclaims the worktrees of merged work before it creates the worktree of the issue. `reclaim_merged_worktrees` inventories the worktrees, reads each merged pull request, then removes each removable one (`src/devops_cli/git/worktree_add.py`).
- The removal is one `git worktree remove` per worktree, in `prune_worktrees` (`src/devops_cli/git/worktree_inventory.py`). It decides every worktree before it removes one, so a failed GitHub read ends the run with nothing removed.
- When two runs start for the same merged worktree, both decide it removable and both send the removal. The first `git worktree remove` succeeds. The second fails, and its worktree is reported as `failed`. `reclaim_merged_worktrees` then sets `reclaim_error`, and the run prints "The merged worktrees were not reclaimed."

## What Changes

- A `git worktree remove` that fails because the worktree is not a working tree is reported as `removed`, not `failed`. `prune_worktrees` detects the message of git and counts the worktree as done.
- The new constant `CONST_GIT_NOT_A_WORKTREE_TOKEN` holds the message of git, `is not a working tree`.
- `reclaim_merged_worktrees` reports the worktree in `reclaimed` and sets no `reclaim_error`, so `add` exits 0 and prints no warning.
- A user sees no false warning when a run in parallel removed a merged worktree, so the change has a spec delta to the two requirements that report the removal of a merged worktree.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-prune`: a worktree that a run in parallel already removed is reported as removed, not as a failed removal.
- `repos-worktrees-add`: a worktree that a run in parallel already removed is not a failed reclaim, and the run says nothing of it.

## Impact

- `src/devops_cli/config/constants.py`, `src/devops_cli/git/worktree_inventory.py`.
- `tests/test_repos_worktrees_reclaim.py`.

## Feasibility

Checked on origin/main on 2026-10-28.

- `git worktree remove` of a worktree whose record is gone fails with return code 128 and says `fatal: '<path>' is not a working tree` on its error stream. Verified on the git in this environment.
- `git_message` reads the error stream of a failed git command, so the token is present when the worktree is gone and absent otherwise.
- The token is specific. `is not a working tree` is the text of this one git error. A real failure of `git worktree remove` (a locked worktree, a dirty worktree, a refused `--force`) says a different thing, and is still reported as `failed`.
- `reclaim_merged_worktrees` builds its `reclaim_error` only from items with `failed` status and its `removed` only from items with `removed` status. Reporting the worktree as `removed` clears both the warning and the error.
- The existing test `test_add_succeeds_when_merged_worktree_file_is_deleted_during_reclaim` already drives the same size walk through a missing file with a fake `os.lstat`, so a test can drive the parallel removal without a second process.

## Existing Tool Considered

The fix is one condition in `prune_worktrees`. A lock or a per-worktree file cannot help: the two runs already share the repository and the directory, and a lock adds a file, a write and a race of its own. `git worktree remove --force` fails on a worktree that is gone as well, so it does not change the message. The change adds the message check where the removal already happens, and deletes no code.

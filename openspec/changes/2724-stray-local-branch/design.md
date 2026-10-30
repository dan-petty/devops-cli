# Design

## Decisions

- **One place: `add_worktree`.** Stage, implement and the command already share `add_worktree`. The helper `_clear_stray_branch` lives in `git/worktree_add.py` beside `_commands`, so the three callers share it and none holds a copy. `stage.py` and `implement_run.py` change nothing.
- **Both paths.** The create path and the take-over path both end in `git worktree add -b <branch>`. Both fail with a stray branch of that name, so both call the helper. The take-over path calls it after `_check_authors`, so a refused takeover deletes nothing.
- **After the fetch.** The helper compares with `origin/main` and with `refs/remotes/origin/*`. The fetch of the create path refreshes `origin/main`. The fetch of the take-over path refreshes `origin/<branch>`. The helper runs after the fetch, so the comparison uses fresh refs.
- **The test for "unpushed".** `git rev-list --count <branch> --not origin/main --remotes=origin`. A commit counts as held when `origin/main` or any remote-tracking ref of `origin` reaches it. A remote-tracking ref can be stale. A stale ref only keeps a branch; it never deletes one. A wrong keep is loud and loses nothing. A wrong delete would lose work.
- **Keep means stop.** A stray branch with unpushed commits makes `add_worktree` raise `GitOperationError`. The message names the branch and the number of commits. Stage and implement record the item as failed for the round with that message, and `devops repos worktrees add` exits 1. This is the same path as every other refusal of `add_worktree`.
- **The held-issue rule stays.** `local_holder` and `issue_holder` still ignore a local branch with no worktree. Their text says that `prune` leaves such a branch after a merge, and a branch of another slug is no conflict. Only the exact name that git would refuse is cleared or named.
- **One log line.** The deletion logs `Deleted the stray local branch <branch> at <commit>` through `logging`, because the job output and the Service log are the places a person looks.

## Rejected alternatives

- **Add `-B` (`git worktree add -B`).** `-B` resets the branch to the start point. It would drop the commits of a stray branch with no check. The rule "never delete a branch that holds unpushed commits" rules it out.
- **Delete in `stage.py` and `implement_run.py` before the call.** It copies the helper into two modules, and `devops repos worktrees add` keeps the fault. The shared function is `add_worktree`.
- **Make `local_holder` hold the issue for any local branch.** `prune` leaves merged branches on purpose, and the scenario "A local branch with no worktree" in the spec says a branch of another slug holds nothing. The change would stop every issue that was ever worked in the clone.
- **Delete the branch always, after a message.** A stray branch can hold the work of a run that died after a commit. The deletion is safe only when `origin` holds every commit.
- **Compare with `origin/<branch>` only.** A pushed branch that was merged and deleted leaves commits on `origin/main` that the branch reaches. The check against `origin/main` and every remote-tracking ref covers merged work and pushed work with one command.

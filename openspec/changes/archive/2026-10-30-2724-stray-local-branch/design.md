# Design

## Decisions

- **One place: `add_worktree`.** Stage, implement and the command already share `add_worktree`. The helper `_clear_stray_branch` lives in `git/worktree_add.py` beside `_commands`, so the three callers share it and none holds a copy. `implement_run.py` changes nothing; `stage.py` and `implement.py` only pass the branch to the planning rule.
- **Both paths.** The create path and the take-over path both end in `git worktree add -b <branch>`. Both fail with a stray branch of that name, so both call the helper. The take-over path calls it after `_check_authors`, so a refused takeover deletes nothing.
- **Why the takeover deletes a stray branch.** In a takeover the pushed branch is the one the App wrote, and the run fetched it just before. The remote-tracking ref of it is live, so it holds the commits of a stray branch of the same name that were pushed. The check of the authors comes first, so a pushed branch of a person refuses the run and the stray branch stays.
- **After the fetch.** The helper compares with `origin/main` and with `refs/remotes/origin/*`. The fetch of the create path refreshes `origin/main`. The fetch of the take-over path refreshes `origin/<branch>`. The helper runs after the fetch, so the comparison uses fresh refs.
- **The test for "unpushed".** `git rev-list --count refs/heads/<branch> --not origin/main <live refs>`. A live ref is a remote-tracking ref of `origin` whose tip equals the tip that `git ls-remote --heads origin` lists for the same branch. The run already reads that output. A stale ref, for a branch that `origin` deleted or that a push rewrote, is not live, so a commit that only it reaches counts as unpushed. A wrong keep is loud and loses nothing. A wrong delete would lose work. The full ref `refs/heads/<branch>` keeps a tag of the same name from standing in for the branch.
- **The planning side.** `stray_branch_reason(repo_root, branch, remote_heads)` is the one rule. `issue_holder` takes the new branch and returns that reason after the other holders; the stage job passes the branch of the title, and the implement job passes the branch of a Planned item. The implement job also asks it for a Staged item, after the author check, as `add_worktree` does.
- **Keep means stop.** A stray branch with unpushed commits makes `add_worktree` raise `GitOperationError`, and `devops repos worktrees add` exits 1. The jobs do not reach that error for a stray branch: the planning side leaves the item out first, with the same message.
- **The held-issue rule stays.** `local_holder` and `issue_holder` still ignore a local branch with no worktree. Their text says that `prune` leaves such a branch after a merge, and a branch of another slug is no conflict. Only the exact name that git would refuse is cleared or named.
- **One log line.** The deletion logs `Deleted the stray local branch <branch> at <commit>` through `logging`, because the job output and the Service log are the places a person looks.

## Rejected alternatives

- **Add `-B` (`git worktree add -B`).** `-B` resets the branch to the start point. It would drop the commits of a stray branch with no check. The rule "never delete a branch that holds unpushed commits" rules it out.
- **Delete in `stage.py` and `implement_run.py` before the call.** It copies the helper into two modules, and `devops repos worktrees add` keeps the fault. The shared function is `add_worktree`.
- **Make `local_holder` hold the issue for any local branch.** `prune` leaves merged branches on purpose, and the scenario "A local branch with no worktree" in the spec says a branch of another slug holds nothing. The change would stop every issue that was ever worked in the clone.
- **Delete the branch always, after a message.** A stray branch can hold the work of a run that died after a commit. The deletion is safe only when `origin` holds every commit.
- **Count every `--remotes=origin` ref.** A stale ref keeps the commits reachable after `origin` dropped them, so the run would delete work that `origin` does not hold.
- **Run `git fetch --prune origin` first.** The planning side has no fetch, and a prune changes the clone for a read. The `ls-remote` text that the run already holds gives the same answer.
- **Compare with `origin/<branch>` only.** A pushed branch that was merged and deleted leaves commits on `origin/main` that the branch reaches. The check against `origin/main` and every remote-tracking ref covers merged work and pushed work with one command.

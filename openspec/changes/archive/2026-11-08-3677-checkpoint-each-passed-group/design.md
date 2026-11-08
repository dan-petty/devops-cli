# Design

## Decisions

- **Keep the progress of a passed group on the item branch.**: The job pushes each passed group to the item branch with the existing `_push_passed`, which uses the lease push for a Staged item and `_publish` for a Planned item. #3054 already puts `wip:` commits on this branch, and #3645 chose it as the place of kept work.
- **Keep the order of `_groups` and `_start` simple.** The order of one boundary in `_groups` is `_require_unclaimed`, `_check_premise`, `_checkpoint`, then `run_step`. The claim check comes first, so a claim that the check sees pushes nothing. The premise check comes second, so a false premise wastes no push. #4070 and #4071 read this order from main. The order of `_start` is one marks write that holds `implement.base`, then `_sync`, then `_install_hooks`.
- **Push at a boundary only after a group passed in this run.**: `_checkpoint` returns at once while no group passed in this run. A push before group 1 would push only the rebase of the staged plan onto the default branch. It would rewrite the branch and start CI for no passed group. A second Job that resumes pushes at the boundary after its first group.
- **Leave the end boundary as it is.**: The end boundary calls only `_require_unclaimed`. `_push` follows and runs the scoped checks before it pushes, so the last group reaches origin after the scoped checks. A push at the end boundary would put a head on origin before the scoped checks and break the rule that the final push holds a head that passed them.
- **Treat a checkpoint as best effort.**: A failed checkpoint push goes to the log with `print_muted`, as `_keep` does, and sets a flag. The run makes no more checkpoint pushes, and the final push still runs. A Planned item whose draft GitHub refuses is asked once, because `_publish` deletes the branch and a second checkpoint would ask again.
- **Write `implement.base` once in `_start`.**: The value is the sha of `origin/<branch>` for a Staged item, or `new` for a Planned item, in the marks write that `_start` already makes. A record that holds a value keeps it, so a second Job (a retry or a continuation) withdraws to the tip before the first Job and not to the checkpoint of the first Job. A run therefore always holds a base, and `_withdraw` needs no case for a missing one.
- **Withdraw before `apply_return`, in `_return_to_new`.**: Both returns (the `premise` request and the behavior-group check) go through this function. A withdraw that fails raises `_StopError` with `push=False`, so the item is Blocked and is not returned, and the record keeps `implement.base`.
- **Use a lease on both withdraw pushes.**: Staged: `git push --force-with-lease=<branch>:<tracking tip> origin <base>:refs/heads/<branch>`. Planned: `git push --force-with-lease=<branch>:<tracking tip> origin --delete <branch>`, after `git ls-remote --heads origin <branch>` shows the branch, then `close_pull` for the recorded draft. A push of a person after the last push of the job makes the lease fail, and the push of the person stays. The probe in `## Feasibility` of the proposal shows both pushes on git 2.55.0.
- **Say nothing in a new setting.**: The change adds a record key and no setting, so no Settings model and no unknown-key rule changes.

## Rejected alternatives

- **A hidden ref such as `refs/devops/wip/<issue>`.**: It needs fetch, ancestry and reset code in `_start`, cleanup on finish, claim and premise, and a sweep for refs of dead Jobs. It makes a second place for progress next to the `wip:` commits. A push of a custom ref to a real GitHub remote was not tested.
- **No checkpoint.**: The replay in `tests/roadmap/implement/test_roadmap_implement_checkpoint.py` shows that groups 1 and 2 are not on origin when group 3 starts.
- **Stop the item when a checkpoint push fails.**: A checkpoint is a copy of work that the run still holds. A failed copy is no reason to discard the groups that can still run.
- **Retry the checkpoint at every boundary.**: A repeated failure wastes requests and hides the first cause. For a refused draft it asks GitHub again each time.
- **A plain `git push --delete` for a Planned withdraw (the text of the issue).**: It would delete the push of a person. The probe shows that a lease on a delete costs one flag and refuses a stale tip.
- **Force the restore after a failed lease.**: It would overwrite the push of a person. The job cannot name a safe tip to restore.
- **Return the item to New after a failed withdraw.**: The item would lose the evidence of the failed withdraw, and a branch that the job did not create would stay for the next Job.
- **Push at the end boundary.**: See above: the head would reach origin before the scoped checks.
- **Remove the checkpoints on a claim.**: The job no longer owns the item and cannot name a safe restore. The new owner starts from the branch on origin and keeps the passed groups.

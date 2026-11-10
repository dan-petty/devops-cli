# Design

## Decisions

- One function decides the commit to push: `_current_tip`. Both `_push_passed` callers that matter (`_keep` in a step, and `_checkpoint` and `stop` between steps) get a current commit from it. `_push` keeps its own `_sync`.
- Between steps and at a stop, the job rebases the checkout in place. The checkout is clean, and the records stay right: `implement.checked_sha` and `implement.published_sha` compare with the new head, so the checks and the push run again; `self.wip` takes the sha of the new last `wip:` commit, and `stop` writes it to `implement.wip`.
- In a step, the job rebases a copy in a detached worktree under the parent folder of the checkout, which is writable in the runner. The head of the checkout does not move, so `implement.checked_sha` and `implement.published_sha` stay right. `implement.wip` keeps the local sha until the next sync at a boundary or a stop rewrites the local commits. The record is a note and no program reads it.
- The push of a commit that is no head uses the refspec `<sha>:refs/heads/<branch>`. A push of the head keeps the old arguments.
- A conflict goes to the log, and the push goes on with the head. A stop must keep the work on `origin` so that the next Job takes it over, and the final push stops the item with the conflict files, as before. A push that waits for the conflict would lose the work of a killed pod.
- The stage job rebases in the worktree of the item, which is clean after the commit. A conflict aborts the rebase and raises the error of git, so the existing failure path records it.

## Rejected alternatives

- Rebase the checkout in place during a step. The keeper holds the shas of the `wip:` commits and the checkout holds edits, so the step would fail its head check.
- Skip the push of a step when the branch is behind. A pod that dies would lose the work of the group, which `implement.wip` exists to prevent.
- Stop the item at a conflict in the middle of a step. It adds a second stop path to a callback of the keeper, and the final push stops the item with the same files.
- `git replay`. It is experimental and the runner image may lack it.

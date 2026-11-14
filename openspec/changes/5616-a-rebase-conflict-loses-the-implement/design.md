# Design

## Decisions

- **Push the head commit with a lease and no pull request when a `wip:`, checkpoint or stop push conflicts.**: The branch on `origin` is the only copy of the work after the pod ends, and the item has no pull request before the end push, so the push starts no CI run.
- **Push the head at the end push too, and then stop with the class `conflict`.**: An item of one group makes no checkpoint push, so the end push is its only push, and the branch must hold the work before the stop.
- **Write the conflicting paths to `implement.conflict` at the conflict push and clear the record in `_start`.**: The next Job hands the record to its first step and a person reads it, and a new Job clears it in its first record write.
- **Count the passed groups from the `tasks.md` of the item, archived or active.**: The count names the groups whose tasks are all ticked on the branch, which is what the branch holds; `implement.group` holds the last group only, and a branch of an earlier Job may hold more.
- **Reuse `OriginGit.push` for the conflict push and skip the pre-push hook.**: It already passes `--force-with-lease` and `--no-verify`, and the hook `branch-current` refuses a branch that does not hold the default branch, so the hook must be skipped.
- **Keep the push rules in the pull-request capability and the comment rule of a conflict stop in the stops capability.**: The push keeps the work and the record, and the stop writes the comment, so each capability holds the rule that its own scenarios assert.
- **Name the implement Job's exception in `docs/SDLC.md` and the conflict push in `docs/ROADMAP_WORKFLOW.md`.**: Both documents state that a conflict pushes nothing, which the change makes false, and a document that contradicts the code misleads the next reader.

## Rejected alternatives

- **A new module that holds the conflict rule of the push.**: `_push_passed` and `_push` already hold every push of the item branch, and `src/devops_cli/roadmap/implement/git_isolation.py:def push` holds the git call, so a second push path would duplicate both.
- **A plain push after a conflict.**: A plain push fails when the branch moved, and `src/devops_cli/roadmap/implement/git_isolation.py:def push` leases on the remote tip that the job read.
- **Settle the conflict inside the run before the push.**: That rewrites the work of a group, and the stop keeps the branch for a person or a retry, which the continuation rule of `CONTEXT.md` already uses.
- **Name the branch and its last commit in the comment, and no count of passed groups.**: The issue asks the comment of a `conflict` stop to name `docs/TESTING.md`, the item branch and the count of passed groups on it, so the comment names the count from the `tasks.md` of the item.
- **Keep pushing nothing after a conflict, as the code does today.**: `tests/roadmap/implement/test_roadmap_implement_push_current.py:170:def test_a_conflict_at_a_wip_push_and_at_the_stop_pushes_nothing(` asserts the loss that #5616 reports.

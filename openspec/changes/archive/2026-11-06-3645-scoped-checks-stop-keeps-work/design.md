# Design

## The place of the kept work

The item branch, `<type>/<issue>-<slug>`, on `origin`.

- The job already pushes this branch for every other stop (`_push_passed`). A Planned item gets its branch and its draft at that push (`_publish`).
- The next Job takes the branch from `origin` (`add_worktree` in `_worktree`). The groups are ticked, so `_groups` runs no step, and `_push` runs the scoped checks.
- A draft pull request shows the work to a person.

Rejected: a separate ref, such as `refs/implement/<issue>`. The next Job must fetch it, merge it and delete it, and no pull request shows it. That is new code for no gain. Evidence: `_worktree` and `add_worktree` take only a branch.

Rejected: the worktree of the Job. `_worktree` removes the worktree and the local branch when the run ends, so the commits are lost. That is the defect.

## The rule "the Job pushes only a head that passed"

The old rule said that a head that fails a scoped check is not pushed, so any stop in the phase pushed nothing. The new rule has two parts:

1. A finished item is pushed only after the scoped checks pass. The checks stay a filter before the push.
2. A stop pushes the commits that passed their own step, in every phase. A head that failed a scoped check is a draft, never ready: the job stops before `_ready`, and `draft_readiness` answers from the checks of the pushed head.

Why: the scoped checks are a pre-push filter and not a gate. The gate is the required checks of the pull request, and a person merges. The old rule protected nothing that the gate does not protect, and it cost the work of all groups.

Rejected: keep the rule and push nothing. The next Job runs every group again.

Rejected: push only the `wip:` commits. After every group passes there are none.

Rejected: a new rule in `draft_readiness` for a stopped item. The pushed head failed a scoped check, so its own checks refuse or wait, and the job never calls `_ready` for a stopped item.

## The selection of a branch whose change is archived

`_Judge._plan_reason` runs the stage gates on the plan at the head of the branch, and it refused a head with no folder under `openspec/changes/<issue>-`. The job moves the folder to `openspec/changes/archive/<date>-<issue>-<slug>` in its last step before the scoped checks, so every branch that holds the archive commit was left out, and a retry could not take the kept work. Evidence: a test that retries after a stop in the scoped checks got `selected=()` and the reason "The head holds no change folder".

Chosen: `_plan_reason` returns no problem when the head holds the archived change of the issue and no active one (`planned_changes_at` on the head). The gates passed the plan when the job took the item first, and the archive command validates the change. Nothing is left to check.

Rejected: skip the plan check for every item with a recorded branch. A staged branch with an active change still needs it (#3615).

Rejected: a flag in the job record. The tree of the head already says whether the change is archived, and a record can drift from it.

## Which stops keep the work

Every stop in the phase. Each ends the run and removes the worktree, so each loses the same commits.

## The comment

`_StopError.kept_branch` is set by `_scoped_checks` for each stop of the phase. `_kept_note` keeps its `wip:` sentence when `wip:` commits exist. Otherwise, with the flag set and a head past the default branch, it names the branch and the last commit. One function and one call in `stop` cover both cases. The flag is explicit because the plan commit of a staged branch is past the default branch too, and a stop at group 1 has kept nothing.

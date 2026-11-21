# Proposal: #6639

## Why
#6639: fix-checks stops when main moved under the pull request (the main-skew stop, #6116). Branch protection needs an up-to-date branch, so the stop only moves the rebase to nobody. The owner decided on 2026-11-21 that the agent phase rebases as a developer does, with the code of implement (#3702 comment 7065393209).

## What Changes
- `prepare` records the tip of the default branch that its clone read (`onto`) when the judged head does not hold it.
- The agent phase rebases onto `onto` and settles each stop with the rules of implement, moved to `roadmap/phases/rebase.py` (`rebase_onto`, `settle_stop`, `skips_archive_commit`, the index-stage rule). implement calls the same module. A rebase that skipped the archive commit archives the change again in a commit of its own.
- A conflict that the rules do not settle stops the round with a reason that starts with `Conflict: ` and names each file. The round pushes nothing.
- When the change of a rebased branch does not cause the failure, only main does, the round pushes the rebased branch alone with the result `rebased`, so the new head gets new checks.
- After a rebase, `publish` replaces the branch on `onto`: the work, the archive commit, the commits after it and the fix, each one commit, with a lease on the judged head. A branch that holds `onto` gets the fix as one commit on the judged head, as before.
- Delete the main-skew stop: `BranchChange.main_paths`, its diff, its rule in `judge_scope` and its two tests.
- The change is observable (the commits of a round), so the spec `roadmap-fix-checks` gets a delta.

## Capabilities
- `roadmap-fix-checks`: the runner Job rebases a branch behind main, the repair scope has no main-skew stop, and a failure that only main causes gets the rebase alone (`rebased`).
- `roadmap-watch-row`: the ready path also takes a draft whose result is `rebased`.

## Impact
- A fix-checks round on a branch behind main rebases and pushes an up-to-date branch.
- fix-checks results have no failure class: a conflict is the result `stopped` with its reason.
- The change fits one pull request.

## Feasibility
- `implement_run.py` on main holds the rebase of #6670 as methods of `_ItemRun`, which fix-checks cannot call. The smallest piece moved to `roadmap/phases/rebase.py`, and the 1908 tests of `tests/roadmap/implement` pass with implement on that module.
- `clone_branch` already reads the tip of the default branch (`BranchClone.base`), so the agent phase needs no network call.
- The new tests ran with real git: the round behind main and the conflict failed on the old code and pass on the new code.

## Existing Tool Considered
- `git rebase` is the tool. The step adds only the settle rules of implement, which it now shares.
- Deleted internal code: the main-skew stop (`main_paths`), and the copies of `_unmerged`, `_rebase_in_progress` and the settle loop in `implement_run.py`, which moved to the shared module.

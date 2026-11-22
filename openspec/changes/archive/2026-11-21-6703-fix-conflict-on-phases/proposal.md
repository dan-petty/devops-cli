# Proposal: #6703

## Why
#6703: `fix-conflict --confirm` has no phases. It clones, rebases, runs tier 1 and pushes in one process, so it cannot run in the three-container Job of #3700, which waits for this item. implement and fix-checks already run on `prepare`, `agent` and `publish`, with the shared code in `roadmap/phases/`. The owner decided on 2026-11-21 that conflicts are settled as a developer does (#3702 comment 7065393209).

## What Changes
- New `roadmap/steps/fix_conflict_phases.py`: `prepare` clones plainly (`clone_branch`) and records `onto` and the judged head; the agent phase rebases with `rebase_onto`, runs tier 1 and the strict spec check, and writes the patches; `publish` pushes them from a new repository with a lease on the judged head, and writes the record.
- `devops roadmap step fix-conflict` takes `--phase prepare|agent|publish|all` and `--work`; `all` keeps the current Job working.
- The round keeps its contract from #6620: one cleanup path, and one more round for each round that reaches the agent phase.
- One archive function, `archive_change`, which fix-checks, fix-conflict and the archive step of implement call.
- The shared rebase loop stops when git refuses `--skip` or `--continue` and stays on the same commit, and the archive skip takes only a commit whose change paths are the item's own.
- `OriginGit` loses its fetch and the write-back of the `shallow` file, which have no caller now; the withdraw of the review step keeps the read of the heads and the push.
- Deleted from `fix_conflict.py`: the clone, fetch and push through `OriginGit`, `resolve_tier1` and its helpers, its own `_archive_again`, `_check_no_human_commit_after_bot`, and the unused `fix_rebase_conflict`.
- The specs `roadmap-fix-conflict` and `roadmap-implement-runner` get a delta, because the command, the push and `OriginGit` change.

## Capabilities
- `roadmap-fix-conflict`: the step runs on the phases, tier 1 runs in the agent phase, and a round gives back the judged head when it does not settle.
- `roadmap-implement-runner`: the network calls of `OriginGit` are the read of the heads and the push.

## Impact
- A hook or a setting that tier 1 writes into the clone changes no pushed round: `publish` works in a new repository.
- With `--confirm`, a branch with a commit that the App did not write fails the round with the message of `clone_branch`, where it was `refused` before. No code reads the result of the step.
- The change fits one pull request. The shared model step for the conflicts that the rules do not settle comes in #6640, after this item.

## Feasibility
- The tests of the step run with real git. The new `reference-transaction` case fails on the code of `main`: the hook runs at the update of the remote-tracking ref after the push. It passes on the phases.
- `clone_branch`, `publish_patch` and `rebase_onto` already serve implement and fix-checks.

## Existing Tool Considered
- `git rebase` and the shared phase code of the project. No tool is built.
- Deleted internal code: the `OriginGit` push of the step, `ensure_checkout` use, `resolve_tier1`, `_take_default_branch`, `_stopped_on`, `_make_again`, `_regenerate_docs_and_commit`, `_regenerate_lock_and_commit`, `_archive_again`, `_is_archive_commit`, `_change_issue`, `_round`, `_settle_rebase_conflict`, `_execute_fix_conflict_in_worktree`, `conflicted_files`, `_abort_rebase`, `_git`, `_check_no_human_commit_after_bot`, `fix_rebase_conflict`, and the `_archive_again` of fix-checks.

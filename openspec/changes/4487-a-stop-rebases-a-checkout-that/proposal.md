# Proposal

## Why

An implement run can stop with files in its checkout that no commit holds. The push of the stop then rebases that checkout, git refuses, and the job pushes a branch that is behind `main`. Closes #4487.

Runner Job `devops-cli-runner-20261111-022552-5e9a` (item #3462) shows it. Group 1 passed and made commit 0c2fc9b5. The archive step moved the change folder and then failed the strict validation of the specs. The stop pushed 0c2fc9b5 without a rebase and logged: "cannot rebase: You have unstaged changes", then "The abort of the rebase failed too. fatal: no rebase in progress". The rebase that did not start also got the class `conflict`, and the job ran `git rebase --abort` with no rebase in progress.

## What Changes

- The push of a stop first puts the checkout back at its head (`git reset --hard HEAD`, `git clean -fd`). A stop pushes only commits, so the files that a failed program wrote are not work that the job keeps. The rebase of the push then finds a clean checkout.
- `_rebase` reads whether a rebase is in progress after git fails. A rebase that git did not start runs no abort, its reason says "The rebase onto origin/<default> did not start.", and the stop has the class `ci_infra` (action `retry`), not `conflict`. A conflict keeps its path: the unmerged files, the abort and the class `conflict`.
- New message `implement_stop_rebase_not_started`. Messages are observable, so the change has spec deltas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The job commits the documentation and the archive, and pushes
- `roadmap-failure-taxonomy`: A rebase that does not start is no conflict (added)

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_push_current.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`
- Documents: `docs/roadmap/implement.md`
- The change fits one pull request.

## Feasibility

The request that started this item said that the formatter of the step leaves its output outside a commit. The evidence refutes that premise. The line numbers are those of `main` before this change.

- `_format_failure` stages each file that `ruff format` changed (`src/devops_cli/roadmap/implement/implement_step.py:1182`). The exit checks run it (`implement_step.py:1551`), and the group commit comes only after every exit check passed (`implement_step.py:1956`). Commit 0c2fc9b5 holds `src/devops_cli/roadmap/stage/stage_change.py`, the file that the log names as formatted (`devops gh api repos/dan-petty/devops-cli/commits/0c2fc9b5`).
- The stop comment on #3462 says "Stopped at archive", with `uv run devops openspec archive 3462-accept-a-test-only-group-that` exit status 1 and "The archive is applied". The archive runs through `_program` (`src/devops_cli/roadmap/implement/implement_run.py:1198`), which raises the stop and leaves the moved folder in the checkout (`implement_run.py:660`).
- `stop` calls `_push_passed` (`implement_run.py:1735`). `_current_tip` calls `_sync` (`implement_run.py:1310`), because its docstring claims "at a stop the checkout is clean" (`implement_run.py:1301`). No code made that true.
- `_rebase` runs `git rebase --abort` after any failure (`implement_run.py:777`) and gives the class `conflict` (`implement_run.py:792`). Git keeps the state of a rebase in progress in `rebase-merge` or `rebase-apply` under the git directory, which `git rev-parse --git-path` names; a refused rebase has neither.
- The class `test` in the log is the class of the archive stop: its output holds "Totals: 258 passed, 1 failed", which the `test` rule of `failure.py` reads. That is a separate defect of the failure rules, and this change does not touch it.
- A test on the base reproduces the log: an archive that moves the folder and exits 1 leaves the branch on `origin` one commit behind `main`, and the log holds the refused rebase and the failed abort.

## Existing Tool Considered

Git covers the need. `git reset --hard` and `git clean -fd` drop the files, as `WipKeeper.discard` does for a stopped step. `git rev-parse --git-path rebase-merge --git-path rebase-apply` names the state directories that git itself reads to know that a rebase is in progress. `git rebase --autostash` was considered and rejected (see `design.md`). The change adds no library and deletes no internal code. Cost: about 20k tokens to build, 3k to keep and fix, about 2 hours.

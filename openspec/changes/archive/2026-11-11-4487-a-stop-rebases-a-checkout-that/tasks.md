# Tasks

## 1. A stop drops the files that no commit holds before its push

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/support/roadmap_implement.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `tests/roadmap/implement/test_roadmap_implement_push_current.py`.

- [x] 1.1 Add a case to `tests/roadmap/implement/test_roadmap_implement_push_current.py`: `main` gains a commit, the archive moves the change folder and exits 1, and the push of the stop holds the commit of `main`. It fails on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py`
- [x] 1.2 Add `_drop_uncommitted` to `implement_run.py` and call it from `_push_passed` when `stop` pushes
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_push_current.py`

## 2. A rebase that does not start is no conflict

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/failure.py`. Changes: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`.

- [x] 2.1 Add a case to `tests/roadmap/implement/test_roadmap_implement_job.py`: a tracked file of the checkout changes before the rebase at the start, the item stops with the class `ci_infra`, and the job runs no `git rebase --abort`. It fails on the base.
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`
- [x] 2.2 Add `_rebase_in_progress` and the message `implement_stop_rebase_not_started`, and make `_rebase` stop with the class `ci_infra` and no abort when no rebase is in progress
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py`

## 3. Documents

Reads: `docs/roadmap/implement.md`. Changes: `docs/roadmap/implement.md`, `src/devops_cli/roadmap/implement/implement_run.py`.

- [x] 3.1 Say in `docs/roadmap/implement.md` and in the module text of `implement_run.py` that a stop drops the files that no commit holds, and that a rebase that does not start is no conflict
  - Verification: `$ uv run devops ci docs`

## Criteria

- Group 1: The push of a stop after a failed archive holds the commit that `main` gained.
- Group 2: A rebase that git does not start stops the item with the class `ci_infra` and runs no abort.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

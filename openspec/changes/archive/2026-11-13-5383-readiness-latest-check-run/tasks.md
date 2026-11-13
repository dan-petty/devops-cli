# Tasks

## 1. The latest run of each check decides

Kind: behavior. Reads: `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`. Changes: `tests/fixtures/github/check_runs_pr_5357_head.json`, `tests/support/recorded_check_runs.py`, `tests/github/test_pr_check_verdict.py`, `tests/commands/test_pr.py`, `src/devops_cli/github/check_verdict.py`.

- [x] 1.1 Record the check runs of the head of #5357, and write the failing tests: an older failure and a newer pass give a pass, the reverse order gives a failure, and `pr ready` and `check-readiness` agree on the recorded head
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/commands/test_pr.py`
- [x] 1.2 Replace `_without_replaced_cancellations` with `_latest_run_of_each_check` in the REST check-runs reader
  - Verification: `$ uv run devops ci test tests/github/test_pr_check_verdict.py tests/commands/test_pr.py tests/github/test_merge_readiness.py`

## 2. Documents

Kind: other. Changes: `docs/roadmap/inbox.md`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stores/github_store.py`.

- [x] 2.1 Say in `docs/roadmap/inbox.md`, and in the docstrings of `_failing_drafts` and `failed_checks`, that a draft of a job is listed when a check of its head commit failed in its latest run
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

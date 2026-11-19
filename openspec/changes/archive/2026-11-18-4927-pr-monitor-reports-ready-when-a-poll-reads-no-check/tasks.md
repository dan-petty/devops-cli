# Tasks

## 1. Behavior

- [x] 1.1 Hold a `checks_unread` blocker in `_judge_checks` when the payload gives no head commit SHA
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py`
- [x] 1.2 Prove the monitor reports a poll with no head commit as not ready with exit code 1
  - Verification: `$ uv run devops ci test tests/github/test_pr_monitor_empty_checks.py`

## 2. Documents

- [x] 2.1 Extend the `pr-merge-readiness` capability
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r main..HEAD).

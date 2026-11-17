# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for a head commit with no check and no pull-request workflow, a
      pull-request workflow, a push-only workflow, and an unread workflow.
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py`
- [x] 1.2 Read the workflow triggers at the head commit and suppress the pending check when no
      workflow can start one.
  - Verification: `$ uv run devops ci test tests/github/test_merge_readiness.py tests/commands/test_pr.py`
- [x] 1.3 Make `devops pr ready` read the verdict's no-CI decision and remove `count_workflows`.
  - Verification: `$ uv run devops ci test tests/commands/test_pr.py`

## 2. Documents

- [x] 2.1 Update the `pr-merge-readiness` specification with the head-workflow rule.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 5144-pr-monitor-fits-a-repository-with`

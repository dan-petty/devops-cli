# Tasks

## 1. Resolve the base dir from the main worktree

Reads: `src/devops_cli/infra/onboard.py`, `src/devops_cli/core/repo.py`.

Changes: `src/devops_cli/infra/onboard.py`, `tests/commands/test_infra_onboard.py`.

- [x] 1.1 Write the test of a relative base dir in a worktree, and watch it fail.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_onboard.py`
- [x] 1.2 Resolve the relative base dir under the main worktree.
  - Verification: `$ uv run devops ci test tests/commands/test_infra_onboard.py tests/infra`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Tasks

## 1. Failing tests

- [x] 1.1 Add failing unit and integration tests with local bare remotes for `fetch_all`, `pull_tracking`, `devops repos sync`, and `devops branches sync`
  - Verification: `uv run devops ci test tests/test_git_operations.py tests/test_repos.py tests/test_branches.py`

## 2. Fail-closed git operations and sync reporting

- [x] 2.1 Update `fetch_all` and `pull_tracking` in `src/devops_cli/git/operations.py` to raise `GitOperationError` with masked stderr, operation, repository, and remote
  - Verification: `uv run devops ci test tests/test_git_operations.py`
- [x] 2.2 Update `devops repos sync` in `src/devops_cli/commands/repos.py` and `devops branches sync` in `src/devops_cli/commands/branches.py` to report failed repositories and exit non-zero
  - Verification: `uv run devops ci test tests/test_repos.py tests/test_branches.py`
- [x] 2.3 Regenerate CLI documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Verification and checks

- [x] 3.1 Verify OpenSpec check passes
  - Verification: `uv run devops openspec check`
- [x] 3.2 Verify full CI suite passes
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

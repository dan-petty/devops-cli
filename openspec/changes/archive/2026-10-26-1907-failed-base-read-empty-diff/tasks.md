# Tasks

## 1. Empty Pull Request Diff

- [x] 1.1 Add failing test in `tests/test_github_client.py` asserting an empty diff body returns an empty string without raising `GitHubUnreadError` (`uv run devops ci test tests/test_github_client.py`)
- [x] 1.2 Implement empty diff body handling in `src/devops_cli/github/session_transport.py` and `src/devops_cli/github/client.py` (`uv run devops ci test tests/test_github_client.py`)
- [x] 1.3 Regenerate documentation (`uv run devops docs generate --sync-readme`)

## 2. Pull Request File Listing Deduplication

- [x] 2.1 Add failing test in `tests/test_pr_cmd.py` verifying pull request changed files read via `GitHubClient.get_pull_files` (`uv run devops ci test tests/test_pr_cmd.py`)
- [x] 2.2 Replace `_fetch_pr_files` and `_changed_file` in `src/devops_cli/commands/pr.py` with `GitHubClient.get_pull_files` and add default counts in `src/devops_cli/github/client.py` (`uv run devops ci test tests/test_pr_cmd.py`)
- [x] 2.3 Regenerate documentation (`uv run devops docs generate --sync-readme`)

## 3. Base Revision Read Errors as Review Coverage Gaps

- [x] 3.1 Add failing test asserting failed base revision file reads produce coverage gaps with reasons in `tests/test_review_scope.py` (`uv run devops ci test tests/test_review_scope.py`)
- [x] 3.2 Update `_write_base_revision_files`, `_write_base_revision_lockfiles`, and `_evaluate_session_complexity_deltas` to record coverage gaps, and remove broad exception swallowing in `_run_static_scanners` and `_run_review_evidence` in `src/devops_cli/ai/review/pipeline.py` (`uv run devops ci test tests/test_review_scope.py`)
- [x] 3.3 Regenerate documentation and verify OpenSpec check (`uv run devops docs generate --sync-readme && uv run devops openspec check`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

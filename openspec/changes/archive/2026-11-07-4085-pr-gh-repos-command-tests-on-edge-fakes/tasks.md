# Tasks

## 1. The gh helpers (test-only edits)

- [x] 1.1 Add `tests/support/gh_process.py` with `gh_edge`, `answer_gh`, `script_gh`, `mentions`, `answer_origin`, `fresh_quota` and `gh_argv`, and `ProjectGitHub.install` in `tests/project_reconcile_fake.py`
  - Verification: `$ uv run devops ci test tests/github/test_github_projects_reconcile.py`

## 2. The repos, gh and pr command tests patch no name (test-only edits)

- [x] 2.1 Move `tests/commands/test_repos.py` to `config`, `process_fake` and `github_api`
  - Verification: `$ uv run devops ci test tests/commands/test_repos.py`
- [x] 2.2 Move `tests/commands/test_gh_cmd.py` and `tests/commands/test_github_milestones.py` to `gh_edge`, `roadmap_store`, `github_api_and_gh` and `clock`
  - Verification: `$ uv run devops ci test tests/commands/test_gh_cmd.py tests/commands/test_github_milestones.py`
- [x] 2.3 Move `tests/commands/test_pr_cmd.py` and `tests/commands/test_pr_update.py` to `gh_edge`, `roadmap_store`, `github_api_and_gh`, `clock` and `mcp_dispatcher`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_cmd.py tests/commands/test_pr_update.py`
- [x] 2.4 Move `tests/commands/test_pr_status.py`, `tests/commands/test_pr_title_labels.py`, `tests/commands/test_pr_form_check.py` and `tests/commands/test_pr_dry_run.py` to `gh_edge` and `roadmap_store`
  - Verification: `$ uv run devops ci test tests/commands/test_pr_status.py tests/commands/test_pr_title_labels.py tests/commands/test_pr_form_check.py tests/commands/test_pr_dry_run.py`

## 3. Documents

- [x] 3.1 Describe `gh_edge` and `ProjectGitHub.install` in `docs/TESTING.md`
  - Verification: `$ uv run devops ci docs`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `$ uv run devops openspec archive 4085-pr-gh-repos-command-tests-on-edge-fakes`

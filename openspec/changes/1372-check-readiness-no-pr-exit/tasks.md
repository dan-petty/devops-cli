# Tasks

## 1. Failing tests

- [x] Add failing offline test for `check-readiness` with no open pull request in `tests/test_pr_cmd.py`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`
- [x] Add failing offline test for `monitor` with no open pull request in `tests/test_pr_cmd.py`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`

## 2. Command exit seam

- [ ] Configure `exit_on=GitHubOperationError` on `app` and `threads_app` in `src/devops_cli/commands/pr.py`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`
- [ ] Remove manual exception catch in `_resolve_monitor_pr_number` in `src/devops_cli/commands/pr.py`
  - Verification: `uv run devops ci test tests/test_pr_cmd.py`
- [ ] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Static checks and OpenSpec validation

- [ ] Verify fail-to-pass check run passes against base
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] Verify full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

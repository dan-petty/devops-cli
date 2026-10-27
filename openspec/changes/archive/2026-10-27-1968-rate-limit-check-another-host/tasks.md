# Tasks

## 1. Store no quota from a rate-limit check that names another host

- [x] Add a failing test for a `gh api rate_limit --hostname` check that leaves github.com quotas unchanged
  - Verification: `uv run devops ci test tests/test_github_rate_limiter.py`
- [x] Return the `--hostname` option value as `GhApiArgs.hostname` in `parse_gh_api_args`
  - Verification: `uv run devops ci test tests/test_github_rate_limiter.py`
- [x] Return false from `_prints_rate_limit_answer` when the named host differs from `CONST_GITHUB_HOST`
  - Verification: `uv run devops ci test tests/test_github_rate_limiter.py`
- [x] Sync documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Archive the change
  - Verification: `uv run devops openspec archive 1968-rate-limit-check-another-host`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for a timeout that the second attempt answers, every attempt
      timing out, an `OSError`, a nonzero exit, and the kept token.
  - Verification: `$ uv run devops ci test tests/core/test_github_auth_token.py`
- [x] 1.2 Retry the timed-out lookup up to `DEFAULT_GH_AUTH_TOKEN_ATTEMPTS` attempts.
  - Verification: `$ uv run devops ci test tests/core/test_github_auth_token.py`

## 2. Documents

- [x] 2.1 Update the `github-app-identity` specification.
  - Verification: `$ uv run devops openspec check`
- [x] 2.2 Archive the change into the main specification.
  - Verification: `$ uv run devops openspec archive 4940-slow-gh-auth-token-on-a-loaded-host`

# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests for the App's failed mint and for a second lookup
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py`
- [x] 1.2 Raise for the App's network git child, keep no failed lookup, and remove the 60 second window
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/github/test_github_app_identity.py`

- [x] 1.3 Raise `GitHubUnreadError` for a mint that GitHub does not answer, and use the kept token after a failed renewal
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py`

## 2. Documents

- [x] 2.1 Add the requirements to the `subprocess-environment` and `github-app-identity` specs
  - Verification: `$ uv run devops openspec check`

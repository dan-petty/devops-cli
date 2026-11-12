# Tasks

## 1. The permissions of each token (behavior)

- [x] 1.1 Write failing tests: the token of a runner Job asks for the permissions of the roadmap jobs with no `repository_hooks` and no `administration`, and its HTTP 422 error names neither
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py`
- [x] 1.2 Add `CONST_GITHUB_APP_METRICS_TOKEN_PERMISSIONS` and ask for it only in a token that names no repository
  - Verification: `$ uv run devops ci test tests/github/test_github_app_identity.py tests/github/test_hook_deliveries.py tests/github/test_github_metrics.py`

## 2. Documents

- [x] 2.1 State the two sets in ADR 0015, in `k8s/README.md` (setup step 1, Webhook route) and in the docstring of the traffic reader
  - Verification: `$ uv run devops ci docs`

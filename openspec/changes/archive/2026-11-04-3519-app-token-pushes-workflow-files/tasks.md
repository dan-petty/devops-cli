# Tasks

## 1. Each token asks for the workflows permission (behavior)

- [x] 1.1 Change the tests: the body of the token request holds `workflows: write`, the log of a minted token names `workflows`, and the HTTP 422 message names `workflows (write)`.
  Verification: `uv run devops ci test tests/github/test_github_app_identity.py`
- [x] 1.2 Add `workflows: write` to `CONST_GITHUB_APP_TOKEN_PERMISSIONS`.
  Verification: `uv run devops ci test tests/github/test_github_app_identity.py`

## 2. Documents (documents)

- [x] 2.1 Update ADR 0015 and `k8s/README.md` with the new list and the risk, and regenerate the documentation with `devops docs generate --sync-readme`.
  Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release image reaches the cluster, clear the block on dreamscaper issue 4 and confirm that its push succeeds.

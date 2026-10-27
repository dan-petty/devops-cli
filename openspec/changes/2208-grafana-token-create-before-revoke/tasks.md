# Tasks

## 1. Reorder the Grafana mint

- [x] Write the failing tests for the order create, store, revoke, for a failed create, and for a refused revoke
  - Verification: `uv run devops ci test tests/test_k8s_credentials.py`
- [x] List the old tokens, create and store the new token, then revoke the old tokens in `mint_grafana_token`
  - Verification: `uv run devops ci test tests/test_k8s_credentials.py`
- [x] Run full CI quality checks
  - Verification: `uv run devops ci`

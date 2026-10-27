# Tasks

## 1. Message of a missing Grafana admin password

- [x] Add a failing test for the message of a missing keyring entry
  - Verification: `uv run devops ci test tests/test_k8s_credentials.py`
- [x] Print the message for a missing `grafana` credential in `_report_credential_sync`
  - Verification: `uv run devops ci test tests/test_k8s_credentials.py`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Archive the change
  - Verification: `uv run devops openspec archive 2209-grafana-missing-password-message`

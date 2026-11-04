# Tasks

## 1. Find a plaintext secret at any depth

Kind: behavior. Reads: `src/devops_cli/config/env.py` lines 166 to 168 (`secret_keys`). Changes: `src/devops_cli/commands/config.py`, `tests/commands/test_config_audit_keys.py`.

- [x] 1.1 In `tests/commands/test_config_audit_keys.py`, add a test for a plaintext value at `grafana.token` and at `service.github_app.private_key`, and a test for a credential key with no value. Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 In `src/devops_cli/commands/config.py`, replace the two-level loop of `_scan_yaml_for_secret_keys` with a walk of the parsed YAML at any depth. Verification: `uv run devops ci test tests/commands/test_config_audit_keys.py`

## 2. Archive

Kind: documentation. Reads: none. Changes: `openspec/changes/`, `openspec/specs/`.

- [x] 2.1 In the last commit, archive the change with `uv run devops openspec archive 2511-audit-keys-nested-secret`. Verification: `uv run devops openspec check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

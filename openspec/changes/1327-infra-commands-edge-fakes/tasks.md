# Tasks

## 1. Domain Logic Extraction

- [ ] Add failing test asserting public domain helpers for Terraform resolution, secret leaks, Cloudflare bypass, and Vault path validation: `uv run pytest tests/invariants/test_architectural_invariants.py`
- [ ] Move Terraform binary resolution from `commands/tf.py` to `tf/` and expose public functions: `uv run pytest tests/commands/test_tf.py`
- [ ] Move secret-leak detection from `commands/config.py` to `config/` and update `tests/test_zero_plaintext_invariants.py`: `uv run pytest tests/invariants/test_zero_plaintext_invariants.py`
- [ ] Move Cloudflare bypass-IP resolution and Vault path validation logic to public domain functions: `uv run pytest tests/commands/test_cloudflare_commands.py tests/commands/test_vault_cmd.py`
- [ ] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## 2. Refactor Config and Vault Command Tests

- [ ] Refactor `test_config_cmd.py` to use `cli` and `keyring_store` without monkeypatching internals: `uv run pytest tests/commands/test_config_cmd.py`
- [ ] Refactor `test_config_commands.py` to use edge fakes without monkeypatching internals: `uv run pytest tests/commands/test_config_commands.py`
- [ ] Refactor `test_config_audit_keys.py` to use `cli` and edge fakes: `uv run pytest tests/commands/test_config_audit_keys.py`
- [ ] Refactor `test_vault_cmd.py` to use `process_fake` and public interfaces without monkeypatching internals: `uv run pytest tests/commands/test_vault_cmd.py`
- [ ] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## 3. Refactor Terraform, Kustomize, and Docker Command Tests

- [ ] Refactor `test_tf.py` to use `process_fake`, `--dry-run` parameter, and `cli` fixture: `uv run pytest tests/commands/test_tf.py`
- [ ] Refactor `test_tf_notify_plan.py` to use edge fakes: `uv run pytest tests/commands/test_tf_notify_plan.py`
- [ ] Refactor `test_kustomize.py` to use `process_fake` without monkeypatching internals: `uv run pytest tests/commands/test_kustomize.py`
- [ ] Refactor `test_docker.py` to use `process_fake` / docker edge fakes without internal monkeypatches: `uv run pytest tests/commands/test_docker.py`
- [ ] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## 4. Refactor Telemetry and Metrics Command Tests

- [ ] Refactor `test_telemetry_cmd.py` to use `otlp` / collector seam and `cli`: `uv run pytest tests/commands/test_telemetry_cmd.py`
- [ ] Refactor `test_telemetry_profile.py` to use edge fakes without monkeypatching `query_jaeger_trace`: `uv run pytest tests/commands/test_telemetry_profile.py`
- [ ] Refactor `test_prometheus.py` to use `respx` / `http_fake` without monkeypatching `load_settings`: `uv run pytest tests/commands/test_prometheus.py`
- [ ] Refactor `test_grafana.py` to use `http_fake` without monkeypatching internals: `uv run pytest tests/commands/test_grafana.py`
- [ ] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## 5. Refactor Network and Runtime Command Tests

- [ ] Refactor `test_cloudflare_commands.py` to use `http_fake` and settings fixtures without monkeypatching `_resolve_client`: `uv run pytest tests/commands/test_cloudflare_commands.py`
- [ ] Refactor `test_argo.py` to use `http_fake` and `process_fake` without monkeypatching internals: `uv run pytest tests/commands/test_argo.py`
- [ ] Refactor `test_valkey.py` to use `valkey_fake` without faking raw sockets or patching `_resolve_client`: `uv run pytest tests/commands/test_valkey.py`
- [ ] Refactor `test_tls_cmd.py` to use edge fakes: `uv run pytest tests/commands/test_tls_cmd.py`
- [ ] Refactor `test_scan.py` to use scanner edge fakes without monkeypatching internals: `uv run pytest tests/commands/test_scan.py`
- [ ] Synchronize CLI documentation: `uv run devops docs generate --sync-readme`

## 6. Verification and Change Archival

- [ ] Run full test suite across all 17 refactored files: `uv run pytest tests/commands/test_*.py`
- [ ] Verify architectural invariants and swallowed failure ratchet tests pass: `uv run pytest tests/invariants/`
- [ ] Run full fast static checks: `uv run devops ci`
- [ ] Archive change folder with `uv run devops openspec archive 1327-infra-commands-edge-fakes`: `uv run devops openspec validate`

## Workflow follow-up
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

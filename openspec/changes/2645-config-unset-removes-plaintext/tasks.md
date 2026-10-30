# Tasks

## 1. A removal of a credential leaves no copy that holds its value

- [x] 1.1 Add the removal tests to `tests/config/test_config_key_removal.py`, the command test to `tests/commands/test_config.py` and the alert test to `tests/test_config_audit_keys.py`, verified to fail with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `CONST_CONFIG_REDACTED_VALUE`, the `redact` parameter of `back_up` with `_copy`, `_redact` and `credential_paths` in `src/devops_cli/config/write_history.py`, and pass the credentials of the removed key from `remove_config_key`, verified with `uv run devops ci test tests/config/test_config_key_removal.py tests/commands/test_config.py tests/test_config_write_history.py`
- [x] 1.3 Delete the sentence about the copy from `ConfigMessages.plaintext_alert`, verified with `uv run devops ci test tests/test_config_audit_keys.py`
- [x] 1.4 Change the help of `devops config unset` and `devops config audit-keys`, `src/devops_cli/docs/generator.py` and the knowledge base, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 2. Archive

- [ ] 2.1 Archive this change with `uv run devops openspec archive 2645-config-unset-removes-plaintext`

## Workflow follow-up

- A plaintext secret under a key with more than two levels, such as `service.github_app.private_key`: #2511.
- `devops config unset` ends with a `TypeError` for a key that a YAML merge key gives: #2656.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. The audit scans each config file that the settings merge

- [x] 1.1 Add `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file` to `tests/test_config_audit_keys.py`, with a project file that `DEVOPS_CLI_CONFIG` names and with one that the directory walk finds, verified to fail on `origin/main` with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `config_layer_paths()` to `src/devops_cli/config/settings.py`, read the files of the settings from it in `_merged_config_data` and in the error of an unknown key in `load_settings`, and make `audit_keys_cmd` in `src/devops_cli/commands/config.py` scan its files in place of `get_active_config_path()`, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/test_config_settings_cache.py tests/test_zero_plaintext_invariants.py`
- [ ] 1.3 Name the scanned files in the docstring of `audit_keys_cmd`, and regenerate the documents with `uv run devops docs generate --sync-readme`, verified with `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

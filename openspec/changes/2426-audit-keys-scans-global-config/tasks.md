# Tasks

## 1. The audit scans each config file that the settings merge

- [x] 1.1 Add `test_config_audit_keys_fails_on_a_plaintext_secret_in_the_global_config_file` to `tests/test_config_audit_keys.py`, verified to fail with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `config_layer_paths()` to `src/devops_cli/config/settings.py`, and scan its files in `audit_keys_cmd`, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/test_config_settings_cache.py`
- [x] 1.3 Name the scanned files in the docstring of `audit_keys_cmd`, and run `uv run devops docs generate --sync-readme`, verified with `uv run devops docs check`

## 2. The report names the file of a leak and shows no text of a file that the audit cannot load

- [x] 2.1 Add `test_config_audit_keys_reports_a_global_config_file_that_the_yaml_loader_cannot_load_unaudited`, verified to fail before 2.2
- [x] 2.2 Catch `_YAML_LOAD_ERRORS` in `_scan_yaml_for_secret_keys`, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/config/test_config_file_that_is_not_yaml.py`
- [x] 2.3 Expect the full path of the file in each leak in `tests/test_config_audit_keys.py`, verified to fail before 2.4
- [x] 2.4 Name the full path of the file in each leak, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/test_zero_plaintext_invariants.py`

## Workflow follow-up

- A plaintext secret under a key with more than two levels, such as `service.github_app.private_key`: #2511.
- A `devops config` command that removes a plaintext secret from a config file that is not the active file: #2513.
- The items of #2451 for `config/write_history.py` and `config/round_trip.py`: #2451.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

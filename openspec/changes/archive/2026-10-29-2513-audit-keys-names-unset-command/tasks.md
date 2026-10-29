# Tasks

## 1. The alert names a command that removes a leak

- [x] 1.1 Add the alert test (a leak in the global file, and a leak in `config.yaml` of the current directory) and the help test to `tests/test_config_audit_keys.py`, verified to fail with `uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add `ConfigMessages.plaintext_alert`, print it in `audit_keys_cmd`, and name the command in the docstrings of `audit_keys_cmd` and `unset_value`, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/commands/test_config.py`
- [x] 1.3 Name the command in `src/devops_cli/docs/generator.py` and in the knowledge base, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 2. The flow of the alert keeps a multi-line credential whole, warns about the copy, and prints for any name

- [x] 2.1 Add `test_the_flow_that_the_alert_names_keeps_a_multi_line_credential_whole`, `test_config_audit_keys_alert_says_to_quote_the_values_and_to_delete_the_copy` and `test_config_audit_keys_prints_each_alert_for_a_name_that_holds_markup` to `tests/test_config_audit_keys.py`, verified to fail before 2.2
- [x] 2.2 Name `--from-file <path>`, the quotes and the copy in the alert, and use `safe=True` for the two lines, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/commands/test_config.py`
- [x] 2.3 Name `--from-file <path>` and the copy in the help, in `src/devops_cli/docs/generator.py` and in the knowledge base, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- A copy `<name>.bak-<YYYYMMDD-HHMMSS>` that `devops config unset` makes still holds the plaintext secret that the command removes: #2645.
- `devops config unset` ends with a `TypeError` for a key that a YAML merge key gives: #2656.
- A plaintext secret under a key with more than two levels, such as `service.github_app.private_key`: #2511.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

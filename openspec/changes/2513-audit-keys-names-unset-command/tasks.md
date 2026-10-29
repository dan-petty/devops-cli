# Tasks

## 1. The alert of audit-keys names a command that removes a leak

- [ ] 1.1 Add `test_config_audit_keys_alert_names_a_command_that_removes_the_leak_from_its_file` (a leak in the global file, and a leak in `config.yaml` of the current directory) and `test_the_help_of_audit_keys_and_unset_name_the_command_that_removes_a_leak` to `tests/test_config_audit_keys.py`, verified to fail with `uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 Add `ConfigMessages.plaintext_alert`, print it in `audit_keys_cmd`, and name the command in the docstrings of `audit_keys_cmd` and `unset_value`, verified with `uv run devops ci test tests/test_config_audit_keys.py tests/commands/test_config.py`
- [ ] 1.3 Name the command in `src/devops_cli/docs/generator.py` and in the knowledge base, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## Workflow follow-up

- A copy `<name>.bak-<YYYYMMDD-HHMMSS>` that `devops config unset` makes still holds the plaintext secret that the command removes: #2645.
- A plaintext secret under a key with more than two levels, such as `service.github_app.private_key`: #2511.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

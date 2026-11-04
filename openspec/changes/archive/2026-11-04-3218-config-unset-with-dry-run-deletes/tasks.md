# Tasks

## 1. Make a dry run of config unset write nothing and print the redacted diff

Reads: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/write_history.py`, `src/devops_cli/output/console.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`.
Changes: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`.

- [x] 1.1 In `tests/config/test_config_key_removal.py`, add failing tests near line 119 for dry-run removal of a block scalar credential, a section removal (`unset ai`), and a credential whose value a comment line also holds, asserting that the returned diff replaces secrets with `CONST_CONFIG_REDACTED_VALUE`, that no diff line holds the value (also not as a comment line), and that nothing is written. In `tests/commands/test_config.py`, rewrite `test_config_unset_dry_run_runs_as_no_external_request` to run `devops --dry-run config unset ai.vllm_url` and assert exit 0, unchanged file text, no backup file, and unified diff output. Add a command test for credential unset dry run. Verify that `uv run devops ci test tests/config/test_config_key_removal.py tests/commands/test_config.py` fails on the base code
- [x] 1.2 In `src/devops_cli/config/settings.py`, update `remove_config_key` to redact the text of the file with `write_history.redact_credentials` and `credential_paths`, and to build `diff` from the redacted text on both sides: the redacted text, and the redacted text with the key removed. `content` for the live write stays unredacted
- [x] 1.3 In `src/devops_cli/commands/config.py`, update `unset_value` to check `is_dry_run()`, pass `dry_run=is_dry_run()` to `remove_config_key`, and render the result with `render_dry_run_result(command=CONST_CONFIG_UNSET_COMMAND, action="remove_config_key", target=removal.path, details={"key": removal.key, "line": removal.line, "diff": removal.diff.splitlines()})` before returning
- [x] 1.4 In `src/devops_cli/lang/en/help.py`, remove the unused `unset_dry_run` attribute from `ConfigCommandHelp`
- [x] 1.5 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check` passes. `docs/CONFIGURATION.md:18` stays unchanged on purpose

## Criteria

- A dry run of `devops --dry-run config unset` writes no configuration file and creates no backup file.: group 1
- The dry-run diff replaces credentials with `CONST_CONFIG_REDACTED_VALUE` for single keys, block scalars, and removed sections.: group 1
- The command renders dry-run output with `render_dry_run_result`.: group 1
- `tests/commands/test_config.py` and `tests/config/test_config_key_removal.py` assert the dry-run behavior.: group 1
- Generated documentation and readme remain synchronized.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Design

## Decisions

- **Pass the dry-run state from the command to `remove_config_key` and print `removal.diff`.**: The removal result already holds the diff and the write decision, so the command needs no second removal path.
- **Redact the value of each credential path from `write_history.credential_paths` as `***REDACTED***` in the dry-run diff.**: That list is the project's source of credential key paths, and `***REDACTED***` is the marker the backup copies already use.
- **Keep the global `--dry-run` option only and add no command-level option.**: `unset_value` already carries `@dry_run_class("no-external-request")` and reads the global flag through `is_dry_run()`, as `set_value` does at `src/devops_cli/commands/config.py:285`.
- **Replace the assertion of `test_config_unset_dry_run_runs_as_no_external_request` with the dry-run behavior.**: The current assertion records the defect and contradicts the spec requirement.

## Rejected alternatives

- **Recompute the diff inside `unset_value` instead of printing `removal.diff`.**: `src/devops_cli/commands/config.py:328` calls `remove_config_key`, which `src/devops_cli/config/settings.py` already implements, so a second diff computation can disagree with the result.
- **Redact by a key name pattern such as `*token*` or `*password*`.**: The issue names `write_history.credential_paths` as the source of the credential key paths, and a pattern would miss a configured credential key.
- **Add a command-level `--dry-run` option to `config unset`.**: `tests/commands/test_config_workspace_docs_dry_run.py` classifies `(unset_value, "no-external-request")` under the global dry-run decorator, so a second option adds a second path with no need.
- **Keep the old removal assertion and add a new dry-run test beside it.**: The old assertion at `tests/commands/test_config.py:158` asserts that the dry run removes the line, so it fails the new behavior.

# Design

## Decisions

- **Perform redaction inside `remove_config_key` in `src/devops_cli/config/settings.py` before building the unified diff**:
  - `unset_value` lacks access to raw file bytes, removed key paths, and `_SECRET_FIELDS`.
  - Replacing diff text line-by-line cannot redact multi-line block scalars because stripped secret lines omit key names.
  - Removing an entire section (such as `devops config unset ai`) deletes multiple keys, including nested credentials.
  - Calling `write_history._redact` on the previous content with `credential_paths(previous, path, _SECRET_FIELDS)` replaces secret values with `CONST_CONFIG_REDACTED_VALUE` (`src/devops_cli/config/constants.py:48`). The diff computed against `content` safely displays `CONST_CONFIG_REDACTED_VALUE`.
- **Render dry-run output via `render_dry_run_result` in `src/devops_cli/output/console.py`**:
  - Call `render_dry_run_result(command=CONST_CONFIG_UNSET_COMMAND, action="remove_config_key", target=removal.path, details={"key": removal.key, "line": removal.line, "diff": removal.diff.splitlines()})`.
  - This preserves standard JSON dry-run output and avoids new message keys.
- **Rely solely on root CLI `--dry-run` flag**:
  - Commit `47cdf0d4` (#2963) intentionally removed `typer.Option("--dry-run", help=HELP.config.unset_dry_run)` from `unset_value` to unify on root CLI `--dry-run` and `@dry_run_class("no-external-request")`.
  - `unset_value` inspects `is_dry_run()` and passes `dry_run=is_dry_run()` to `remove_config_key`.
  - Remove unused `HELP.config.unset_dry_run` from `src/devops_cli/lang/en/help.py`.
- **Keep `docs/CONFIGURATION.md:18` unchanged**:
  - Line 18 of `docs/CONFIGURATION.md` already states: "`--dry-run` prints the change, with the lines of its unified diff, and writes nothing". It remains accurate on purpose.
- **Update tests to verify complete zero secret leakage**:
  - Update `tests/commands/test_config.py:158` to assert the file does not change, no backup file is created, and diff output matches.
  - Add tests in `tests/config/test_config_key_removal.py` for block scalar credential unsetting and full section unsetting (`unset ai`), asserting that the diff contains `CONST_CONFIG_REDACTED_VALUE` and no plaintext secret.

## Rejected Alternatives

- **Post-process diff lines in `unset_value`**:
  - Rejected because `unset_value` lacks raw file bytes and secret taxonomy definitions. Also, block scalars and section removals lack key names on secret lines in diffs.
- **Reintroduce command-level `--dry-run` option to `unset_value`**:
  - Rejected because commit `47cdf0d4` (#2963) deliberately removed command-level dry-run flags across no-external-request commands to standardize on root `--dry-run`.
- **Pattern matching on key names for redaction**:
  - Rejected because `write_history.credential_paths` and `_SECRET_FIELDS` provide the canonical source of truth for secret fields.

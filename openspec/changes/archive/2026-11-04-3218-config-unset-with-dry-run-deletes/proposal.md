# Proposal

## Why

A dry run of `devops config unset` deletes the key and writes a backup file (#3218). The `config-commands` spec states that a dry run writes nothing and prints the removal diff. The current implementation and tests contradict the specification.

## Order and Dependencies

This change supersedes issue #2740 ("devops config unset --dry-run prints the credential that it would remove"). Plan pull request #3158 for #2740 was closed unmerged. This change covers credential redaction in the dry-run diff so maintainers can close #2740.

## What Changes

- Invocation updates from `devops config unset <key> --dry-run` (which exited with code 2) to root CLI invocation `devops --dry-run config unset <key>`.
- In `src/devops_cli/commands/config.py`, `unset_value` checks `is_dry_run()`. It passes the flag to `remove_config_key` and prints the diff.
- In `src/devops_cli/config/settings.py`, `remove_config_key` redacts text with `write_history._redact` before it constructs the diff.
- A dry run writes no configuration file, writes no backup file, and appends no audit record.
- The dry-run diff replaces credentials with `CONST_CONFIG_REDACTED_VALUE` (`***REDACTED***`). This hides single keys, block scalars, and keys in removed sections like `unset ai`.
- Dry-run output uses `render_dry_run_result` from `src/devops_cli/output/console.py`.
- The unused help text `HELP.config.unset_dry_run` is removed from `src/devops_cli/lang/en/help.py`.
- `tests/commands/test_config.py` and `tests/config/test_config_key_removal.py` assert unchanged files, absent backups, and redacted diffs.
- `docs/CONFIGURATION.md:18` already documents that `--dry-run` prints the unified diff and writes nothing. It remains unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: devops config unset --dry-run writes nothing

## Impact

- Code: `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/help.py`
- Documents: `openspec/specs/config-commands/spec.md`
- Tests: `tests/commands/test_config.py`, `tests/config/test_config_key_removal.py`

## Security Considerations

This change enforces SECURITY.md Principle 1 (Zero Secret Leakage). Plaintext secrets must never enter terminal outputs or CI logs. Redacting text before diff generation ensures that neither block scalars nor section removals leak credentials into terminal output.

## Feasibility

Testing against a temporary configuration reproduced the defect:

```
$ devops --dry-run config unset ai.model
exit: 0
stdout:
Removed ai.model from <tmp>/cfg/config.yaml:5.
The file before the change is in <tmp>/cfg/config.yaml.bak-20261102-221355.

$ ls cfg
config.yaml  config.yaml.bak-20261102-221355

$ devops config unset ai.model --dry-run
exit: 2
stderr:
Usage: devops config unset [OPTIONS] {key}
No such option: --dry-run
```

- In `src/devops_cli/commands/config.py` line 328, `unset_value` calls `remove_config_key(key, dry_run=False)` unconditionally.
- In `src/devops_cli/config/settings.py` lines 1651-1658, `remove_config_key` builds the diff from unredacted source text before checking `dry_run`.
- In `tests/commands/test_config.py` lines 158-168, `test_config_unset_dry_run_runs_as_no_external_request` asserts that `--dry-run` removes the key from disk.
- In `tests/config/test_config_key_removal.py` line 119, existing tests only check `remove_config_key("ai.vllm_url", dry_run=True)` on non-secret keys.

## Existing Tool Considered

The CLI already implements `render_dry_run_result` at `src/devops_cli/output/console.py:820`. The command reuses this renderer:

```python
render_dry_run_result(
    command=CONST_CONFIG_UNSET_COMMAND,
    action="remove_config_key",
    target=removal.path,
    details={"key": removal.key, "line": removal.line, "diff": removal.diff.splitlines()},
)
```

The codebase also contains `write_history._redact` and `write_history.credential_paths`. Reusing these existing functions requires no external libraries. Estimated cost is 2,000 tokens to build, keep, and fix, and under one hour of elapsed time.

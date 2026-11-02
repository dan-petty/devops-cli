# Proposal

## Why

A dry run of `devops config unset` deletes the key and writes a backup (#3218). The config-commands spec says a dry run writes nothing and prints the removal diff, and the code and the test disagree with it.

## What Changes

- `unset_value` in `src/devops_cli/commands/config.py` passes the dry-run state to `remove_config_key` and prints the diff of the removal.
- A dry run of `devops config unset` writes no config file, no backup and no history record.
- The dry-run diff shows `***REDACTED***` in place of the value of each credential path from `write_history.credential_paths`.
- `tests/commands/test_config.py` asserts the unchanged file, the absent backup and the redacted diff.
- The `devops config unset --dry-run writes nothing` requirement of the `config-commands` spec states the diff and the redaction.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: devops config unset --dry-run writes nothing

## Impact

- Code: `src/devops_cli/commands/config.py`
- Documents: `openspec/specs/config-commands/spec.md`
- Tests: `tests/commands/test_config.py`

## Feasibility

- `read_file` on `src/devops_cli/commands/config.py` lines 313-334 showed the premise: `def unset_value(` with no `dry_run` parameter, and the body `removal = remove_config_key(key, dry_run=False)` followed by `print_info(MESSAGES.config.unset_backup.format(backup=removal.backup), ...)`. The command never reads `removal.diff`, so a dry run writes.
- `read_spec` of the requirement `devops config unset --dry-run writes nothing` in `config-commands` returned: `SHALL print the dry-run response with the file, the key, its line and the lines of the unified diff of the removal, and SHALL write no file and no audit record`, with the scenario lines `@@ -7 +6,0 @@` and `-  vllm_url: <value>`. The code disagrees with this text.
- `read_file` on `tests/commands/test_config.py` lines 64-91 showed a test that asserts a real removal and a backup file, and the context shows `test_config_unset_dry_run_runs_as_no_external_request` at line 158, the assertion the issue names.
- The probes list `src/devops_cli/commands/config.py`, `tests/commands/test_config.py`, `openspec/specs/config-commands/spec.md` and `tests/commands/test_config_workspace_docs_dry_run.py` as files of the staging commit, and `remove_config_key` has callers in `src/devops_cli/commands/config.py` and `src/devops_cli/config/settings.py`. The issue can be built as written.
- First checks against the real system: `uv run devops ci test tests/commands/test_config.py` fails on the new dry-run assertion before the fix and passes after it; `uv run devops --dry-run config unset ai.provider` in a clone with a two-key config leaves the file and its directory unchanged; `uv run devops openspec check` accepts the spec delta.

## Existing Tool Considered

No open, maintained tool or library covers this need: the defect is in devops-cli's own `config unset` command, and the fix reuses its own `remove_config_key` result. The change edits existing code and adds no code to keep, so the written cost is about 2,000 tokens to build, keep and fix, and under one hour of elapsed time. It deletes no internal code.

# Tasks

## 1. Redact credential values in the unset dry-run diff

Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`, `src/devops_cli/models/config.py`, `src/devops_cli/commands/config.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/models/config.py`, `src/devops_cli/commands/config.py`, `tests/config/test_config_unset_dry_run_redaction.py` (new).

- [ ] 1.1 Write `tests/config/test_config_unset_dry_run_redaction.py` first. It calls `remove_config_key('ai.api_key', target_path=tmp_path/'config.yaml', dry_run=True)` on a file holding `ai.api_key: sk-ant-fake123` and asserts the diff holds `***REDACTED***` and not `sk-ant-fake123`. It also calls the same function for `ai.model: llama3` and asserts the diff holds `llama3`, and verify that `uv run devops ci test tests/config/test_config_unset_dry_run_redaction.py` fails on the base
- [ ] 1.2 In `remove_config_key` in `src/devops_cli/config/settings.py`, after `round_trip.find` returns `path` and `line`, build `diff_text` from `text`. When `path` is in `_SECRET_FIELDS`, set the value at `path` in `diff_text` to `***REDACTED***` with `round_trip.edit`. Compute `difflib.unified_diff` from `diff_text.splitlines()` and `content.splitlines()`. Keep `content` from the original `text`. Update the `diff` field description in `src/devops_cli/models/config.py` and the `unset` help in `src/devops_cli/commands/config.py` to state that the preview redacts credentials, and verify that `uv run devops ci test tests/config/test_config_unset_dry_run_redaction.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

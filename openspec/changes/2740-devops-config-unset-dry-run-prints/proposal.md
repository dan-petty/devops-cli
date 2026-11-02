# Proposal

## Why

The dry-run preview of `devops config unset` prints the credential value in its diff. #2740 reports that the value reaches terminals, scroll-back and CI logs. The change redacts the value in the preview.

## What Changes

- Redact the credential value in the dry-run diff before `difflib.unified_diff` runs.
- Keep non-credential values in the dry-run preview.
- Add a test for a credential key and a non-credential key.
- Update the command help and the model description to state that the preview redacts credentials.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: Dry-run diff redacts credential values

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/models/config.py`, `src/devops_cli/commands/config.py`
- Tests: `tests/config/test_config_unset_dry_run_redaction.py`

## Feasibility

- The inputs confirm the premise: `remove_config_key` in `src/devops_cli/config/settings.py` builds the diff from `text.splitlines()` and `content.splitlines()` with no redaction.
- `_SECRET_FIELDS` is in `src/devops_cli/config/settings.py`, and `write_history.credential_paths` redacts only the backup copy.
- The first check is `uv run devops ci test tests/config/test_config_unset_dry_run_redaction.py`.
- The next check uses a temporary `HOME` and `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring`: `uv run devops config unset ai.api_key --dry-run`.
- A second manual check uses `uv run devops config unset ai.model --dry-run` and expects `llama3` in the diff.

## Existing Tool Considered

No open, maintained tool covers redacting one value in a `difflib.unified_diff` inside this CLI. The change builds its own code: about 2,000 tokens to build, 500 to keep and 1,000 to fix, and under one hour. It deletes no internal code.

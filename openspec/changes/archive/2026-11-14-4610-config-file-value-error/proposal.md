# Proposal

## Why

A validator that refuses a value in a config file raises a pydantic `ValidationError` through `load_settings`. The command prints the pydantic text with its URL and then a traceback, while the same value in an environment variable gives one clean line (#4610).

## What Changes

- `load_settings` converts a refused config-file value into `ConfigurationError` with the file, the setting and the reason.
- The error names the longest declared key prefix, so a list index does not appear.
- A validation error from no config-file key stays as it is.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: A refused config-file value is one `ConfigurationError` line.

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/errors.py`
- Tests: `tests/config/test_config_file_value_errors.py`

## Feasibility

- `load_settings` already catches `ValidationError` for the unknown-key error.
- The layers hold both mappings, so the file that holds the key is known.
- Verification commands: `uv run devops ci test tests/config/test_config_file_value_errors.py tests/config/test_unknown_config_keys.py tests/commands/test_config_commands.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

pydantic gives each error's location and message. The change adapts them into the existing `ConfigurationError`; no new library.

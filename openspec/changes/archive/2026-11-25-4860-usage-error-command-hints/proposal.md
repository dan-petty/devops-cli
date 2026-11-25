# Proposal: #4860

## Why

Usage errors stop agents and people with bare Click messages such as `No such command 'merge'` and `No such option: --json`, even when the CLI stops on purpose, moves a command to another group, splits a hyphenated subcommand, or requires an option without context (#4860). Telemetry records usage errors, but does not tell apart an error that received a hint from an unhandled error.

## What Changes

Add a static command-hint lookup table (`src/devops_cli/core/usage_hints.yaml`) and hint resolver (`src/devops_cli/core/usage_hints.py`), improve Click's unknown-option and missing-option messages, print one hint line after Click's error box while keeping exit code `2`, and add `hinted` to `UsageErrorRecord` and `cli_usage_error` telemetry.

Specific changes:
- Add `by_design` hints for `pr merge` and `gh pr merge` explaining that only a person merges a pull request.
- Add `other_name` synonym hints for `roadmap` (`show`, `view`, `get`, `list`, `status`), `pr` and `gh pr` (`show`, `info`, `comment`), and interim `gh` flags (`--json`, `--jq`, `--comments`, `--search` on `gh issue view|list` and `gh pr view|list`).
- Add `other_tool` hints for `openspec validate` and `openspec list` naming both the OpenSpec CLI command and `devops openspec check`.
- Print all gate row names from `CHECK_ROW_NAMES` in one line when `devops ci list` or `devops ci --list` fails, while exiting `2`.
- Fall back to whole-word cross-group lookup across the command tree (including hyphen/underscore splits such as `ai cost-report` -> `devops ai cost report`), ignoring prefix or partial matches.
- Strip `--help` and `-h` from `Possible options` lists on unknown-option errors; when no close match remains and the command has at most 6 non-help options, list all of them on the error line.
- Append the option's help text to `Missing option` errors.
- Record `hinted: bool` on `UsageErrorRecord`, in `usage-errors.jsonl`, and on `cli_usage_error` (`usage.hinted`), and regenerate `docs/TELEMETRY.md`.

## Capabilities

### Modified Capabilities
- `command-telemetry`: Usage error hints, option error contextualization, and the `hinted` record field.

## Impact

- Single pull request inside `src/devops_cli/core/`, `src/devops_cli/config/constants.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/telemetry/`, `src/devops_cli/docs/`, `docs/TELEMETRY.md`, and `tests/`.
- Cold CLI startup adds zero imports: `usage_hints` loads only when a `UsageError` is handled.

## Feasibility

Confirmed on `origin/main` against source and live CLI runs:
- `src/devops_cli/core/cli.py` already routes every CLI `UsageError` through `UsageTaggedGroup`, `UsageTaggedCommand`, and `UsageRecordingGroup` (#4839) using `typer._click.exceptions`.
- `src/devops_cli/commands/ci.py` exports `CHECK_ROW_NAMES` (#5451).
- `uv run devops pr merge 1`, `uv run devops roadmap show 1`, `uv run devops gh issue view 1 --bogus`, and `uv run devops pr describe 1` all currently exit `2` with no extra hint line, `--help` appears in `Possible options` (`--hel`), and `Missing option` omits option help.

## Existing Tool Considered

Vendored Click (`typer._click`) already provides `NoSuchOption.possibilities`, `MissingParameter.format_message`, and `difflib.get_close_matches` for same-group typos, and `devops_cli.core.command_resolver` already walks lazy `_COMMAND_SPECS` modules. This change reuses both mechanisms rather than writing a custom parser or replacing Click. The static YAML table (`usage_hints.yaml`) and thin resolver (`usage_hints.py`, ~200 lines) handle intentional exclusions, cross-tool redirects, and cross-group splits that difflib cannot express; estimated cost ~3k tokens and <1h, deleting zero external tools and replacing no existing telemetry store.

# Proposal

## Why

Issue #2216: `devops scan` subcommands print a muted progress line to stdout before the JSON payload when `--json` or `--format json` is set. The line is not part of the JSON, so piping the output to `json.loads` fails with `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. JSON on stdout must parse; progress output belongs to table mode only.

## What Changes

- `scan trivy`, `scan secrets`, `scan sast`, `scan iac`, `scan complexity`, `scan workflows` and `scan aibom` resolve the output format before any progress print and print the muted progress line only when the resolved format is table.
- `scan injection` and `scan sbom` already gate their progress output correctly; they need no code change.
- The change adds the capability `scan-json-stdout`: JSON output on stdout of a `devops scan` command parses without any progress output.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `scan-json-stdout`: JSON on stdout of a `devops scan` command is a single valid JSON document.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/scan.py`, `tests/test_scan.py`.

## Feasibility

- Command output: the issue cites the JSON decode failure. At the base commit each scan command calls `print_muted` before `resolve_format`, so the progress line precedes the JSON payload on stdout. The new test `uv run pytest tests/test_scan.py -k json_stdout` fails on every affected subcommand before the fix and passes after it.

## Existing Tool Considered

No outside tool applies. The change reuses `resolve_format`, `emit_serialized` and `print_muted`; it gates the existing progress print on the resolved format.

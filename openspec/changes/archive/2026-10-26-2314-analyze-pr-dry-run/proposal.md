# Proposal

## Why

Issue #2314: `devops ai analyze pr` declares `--dry-run`, but it opens a GitHub session and calls `get_pull` and `get_pull_files` first.
These calls contact the GitHub service. Under #412 and #986, this is external communication in a dry run.

## What Changes

- `analyze pr` checks `--dry-run` and `is_dry_run()` first. It renders `render_dry_run_result` and returns.
- In a dry run the command opens no GitHub session, starts no child process and writes no file.
- The dry-run branches that the check makes dead are removed from the rest of the command.
- The change adds the capability `analyze-pr-dry-run`: a command option is observable behavior.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `analyze-pr-dry-run`: dry-run behavior of `devops ai analyze pr`.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/analyze.py`, `tests/test_analyze.py`.

## Feasibility

- Command output: the issue cites `analyze.py` lines 523 to 524. The code at the base commit calls `session.client.get_pull` before any dry-run check. The new test fails on it.

## Existing Tool Considered

No outside tool applies. The change reuses `render_dry_run_result` and deletes the dead dry-run branches of `analyze pr`.

# Proposal

## Why

A command that the planner runs can print more text than a plan holds, and it can print a credential. ADR 0018 requires the run tool to cap the text at 8 KiB and 120 lines, to mask a secret, and to start the cap after the mask so a private-key block never loses its end marker (#4006).

## What Changes

- Add `src/devops_cli/roadmap/run_output.py`: `MAX_RUN_OUTPUT_BYTES` 8192, `MAX_RUN_OUTPUT_LINES` 120, `cap_run_output` and `quote_run`.
- `cap_run_output` masks with `mask_secrets`, keeps the first whole lines that fit the caps with the trailer, and adds `[truncated: N bytes and M lines omitted]` when it cuts.
- `quote_run` formats the text as a fenced block with the command line and the exit code, and the fence is one backtick longer than the longest run in the text.
- Add `tests/roadmap/test_roadmap_run_output.py` for the caps, the trailer, the mask, the key block and the fence.

## Capabilities

### New Capabilities

- `roadmap-run-output`: the cap, the trailer, the mask and the quote block of one planner run.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/run_output.py`
- Tests: `tests/roadmap/test_roadmap_run_output.py`
- Document: `docs/CLUSTER.md`

## Feasibility

- Read on `origin/main`, 2026-11-14. `src/devops_cli/security/sanitizer.py:454:def mask_secrets(` masks a token, and `:353:lambda match: "<masked-private-key>"` masks a whole PEM block, so the mask must run before the cut.
- The run tool has no code yet (#4098), so this module is the one home of the formatter.
- `uv run pytest tests/roadmap/test_roadmap_run_output.py` passes after the change.

## Existing Tool Considered

`mask_secrets` already masks a credential for 84 callers, and Python string slicing covers the cap. No open, maintained library truncates markdown-safe command output with a counted trailer; the change adds about 1,500 tokens and 150 a quarter to keep.

## Dependencies

#3242 is closed, and ADR 0018 is on the default branch.

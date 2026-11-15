# Proposal

## Why

Pull request #5198 deleted the option `--sync-readme` of `devops docs generate`, and ADR 0010 and ADR 0014 still named it as the command that regenerates the documents. An agent that follows them gets a usage error (#5244).

## What Changes

- Add one dated Status History line to ADR 0010 and ADR 0014: the option is deleted, so the command is `devops docs generate`.
- The body of each record stays as it is, because an accepted record changes only in the front matter and a dated Status History line.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The record of the ADR process already states the Status History line.

## Impact

- Documents: `docs/adr/0010-openspec-is-the-spec-and-change-proposal-layer.md`, `docs/adr/0014-required-checks-gate-the-merge-and-the-pre-push-hook-runs-the-fast-static-checks.md`

## Feasibility

- Read on `origin/main`, 2026-11-15. `docs/adr/README.md` allows one dated line at the end of `Status History` and excludes that section from `body-hash`.
- `uv run pytest tests/docs/test_docs_adr_records.py` passes after the change.

## Existing Tool Considered

The ADR record reader and its test already hold the rule. No tool.

## Dependencies

None.

# Proposal

## Why

ADR 0022 names the rows of the roadmap Service in its text, and the code held seven of them. The eight rows that the plan adds had no name segment, and a name that is not one would make a unit name, a lock name, a component label or a service name invalid (#5290).

## What Changes

- Add `brain`, `resolve`, `group`, `split`, `watch`, `fix-checks`, `fix-conflict` and `fix-plan` to `ServiceRow`.
- Add a test that every row is a name segment of at most 12 characters, that no row is `repair`, and that the eight rows are present.
- Add one dated Status History line to ADR 0022: the row list lives in `ServiceRow`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-names`: the rows of the roadmap Service are name segments.

## Impact

- Code: `src/devops_cli/github/repo_ref.py`
- Tests: `tests/github/test_repo_ref.py`
- Document: `docs/adr/0022-...`

## Feasibility

- Read on `origin/main`, 2026-11-15. `src/devops_cli/github/repo_ref.py:54:class ServiceRow(` holds seven rows.
- Each new value has at most 12 characters and uses letters and a hyphen, so `is_name_segment` accepts it.
- `uv run pytest tests/github/test_repo_ref.py` passes after the change.

## Existing Tool Considered

`ServiceRow` and `is_name_segment` are in the file. The change adds eight values and one test: about 500 tokens to build and 20 a quarter to keep.

## Dependencies

None.

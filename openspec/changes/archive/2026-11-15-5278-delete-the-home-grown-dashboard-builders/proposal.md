# Proposal

## Why

`src/devops_cli/grafana/builders.py` was a second dashboard builder, and no module of `src/` called it: the service dashboards come from the Grafana Foundation SDK (#5184). Only its tests and `grafana/__init__.py` named it (#5278).

## What Changes

- Delete `src/devops_cli/grafana/builders.py` and the builder tests of `tests/grafana/test_grafana_dashboards.py`, and remove the builder names from `grafana/__init__.py`.
- Keep the schema types that the linter reads: `Dashboard`, `Panel`, `Target`, `GridPos` and `Datasource`.
- Keep the linter tests that build their dashboards as schema objects.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change removes code that nothing called.

## Impact

- Code: `src/devops_cli/grafana/__init__.py`, and the deleted `src/devops_cli/grafana/builders.py`
- Tests: `tests/grafana/test_grafana_dashboards.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `git grep -n -e "grafana.builders" -- src tests` finds only `grafana/__init__.py` and the tests.
- `uv run pytest tests/grafana` passes with 107 tests after the change.
- `uv run devops grafana dashboards lint k8s/monitoring/dashboards` gives the same 0 errors and 5 warnings.

## Existing Tool Considered

The Grafana Foundation SDK already builds and lints the committed dashboards. The change deletes about 400 lines and adds none.

## Dependencies

None.

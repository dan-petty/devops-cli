# Proposal

## Why

The stage job leaves an item out while an issue dependency is open, but the implement job checks no dependency. It starts the item, and the run fails or `plan-check` blocks the pull request with the `issue-dependency` rule (#4009).

## What Changes

- `src/devops_cli/roadmap/dependencies.py` holds the shared check for an open body or plan dependency.
- The stage judge uses the shared check, so its reason stays the same.
- The implement judge reads the body dependency and the dependency of the plan proposal, and leaves the item out with the same reason.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/selection`: The implement judge leaves out an item with an open dependency.

## Impact

- Code: `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_selection.py`

## Feasibility

- The stage job already reads the body dependencies and the quoted titles through `body_dependencies` and `title_dependencies`.
- `read_change` already holds the plan dependencies, and `issue_dependencies` parses them.
- Verification commands: `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py tests/roadmap/stage/test_roadmap_stage_selection.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The stage job's check covers the body dependency already. The change moves it to a shared module and gives it one more caller. No library covers a repository-specific declaration.

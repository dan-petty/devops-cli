# Proposal: #6328

## Why

`find_removed_names` in `src/devops_cli/roadmap/stage/stage_removal_references.py` keeps each backticked span after a removal verb when `str.isidentifier()` is true. `"and".isidentifier()` is true, so a plan line such as "drops `and` from the title" makes `and` a removed name. `scan_removal_references` then finds `and` in every Python file under `tests/`, and the stage fails with `RoadmapStageError` (#6328). A Python keyword is never an entity that a plan removes.

## What Changes

- `find_removed_names` keeps a span only when it is an identifier that is not a Python hard keyword (`keyword.iskeyword`) and not a Python soft keyword (`keyword.issoftkeyword`).
- One private helper holds this rule, and the passive and the active match paths both call it.
- The removed names of the stage scan are observable behavior of `devops roadmap stage`, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/references`: one ADDED requirement. A Python keyword is never a removed name.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_removal_references.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_removal_references.py`
- No new dependency.

## Feasibility

- On origin/main with CPython 3.14.10, `find_removed_names("The change drops `and` from the title.")` returns `{'and'}`, `find_removed_names("`and` is removed from the title.")` returns `{'and'}`, and `find_removed_names("The change drops `match` from the title.")` returns `{'match'}`.
- The guard covers a set: on CPython 3.14.10, `keyword.kwlist` has 35 hard keywords and `keyword.softkwlist` has 4 soft keywords (`_`, `case`, `match`, `type`). Each of the 39 passes `str.isidentifier()`, so the current code keeps each of them as a removed name. Command: `uv run python -I -c "import keyword; print(len(keyword.kwlist), keyword.softkwlist)"`.
- `pyproject.toml` sets `requires-python = ">=3.14"`, and both `keyword.iskeyword` and `keyword.issoftkeyword` exist on that floor.

## Existing Tool Considered

The standard-library `keyword` module of python/cpython (`keyword.iskeyword`, `keyword.issoftkeyword`) covers the need. It ships with the interpreter, so it adds no dependency or pin, and its lists follow each new Python release. The change adds a call to this module and deletes no internal code: the project has no keyword list of its own for this check.

# Proposal: #5887

## Why
The strength check of the implement job (#3051) cannot run (#5887). `run_mutation` starts `uv run mutmut run` with the environment key `PYTEST_ADDOPTS`, and the process runner refuses that key with `SecurityError` (#2747), because pytest writes a file at the path that `--junitxml=<path>` names. Since 2026-11-15 05:43Z, three implement runs stopped this way after every group passed (#3387, #3239, #3529). The job gave each stop the class `ci_infra` with the action `retry`, so the Service starts the item again on each new runner image, and each retry fails in the same way. The unit tests replace the process runner, so no test ran the real check of the environment.

## What Changes
- The mutation run gives mutmut the scoped test modules in `pytest_add_cli_args_test_selection` of `[tool.mutmut]` in `pyproject.toml`, and sets no environment key. The run writes the file before `mutmut run` and writes the original bytes back after it, also when the command raises or runs out of time. A checkout with no `pyproject.toml` gets one for the run and has none after it.
- A `SecurityError` that ends an implement run, as from a scoped check command, gives the stop the class `refused_tool` (action `wait`), not `ci_infra`. The rule `digest` does not clear such a stop.
- The env deny list stays as it is: `PYTEST_ADDOPTS` stays refused, with no exception for this caller.
- New runtime dependency: `tomlkit==0.15.2`.
- The change alters observable behavior of the implement job, so it carries spec deltas. It fits one pull request.

## Capabilities
- `roadmap-implement-job/repair`: the mutation run takes its test selection from the mutmut table.
- `roadmap-implement-job/stops`: a command that the process runner refuses stops as `refused_tool`.

## Impact
- `src/devops_cli/roadmap/implement/implement_strength.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/failure.py` (docstring).
- `pyproject.toml` and `uv.lock` (tomlkit).
- `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/implement.md`, the package manual of the knowledge base.
- The items that stopped with `ci_infra` keep that class, so the next runner image with this fix clears them by the rule `digest`.

## Feasibility
- The source of mutmut 3.8.1 in `.venv` (`mutmut/configuration.py`, `_config_reader` and `_load_config`) reads the settings from `[tool.mutmut]` of `pyproject.toml` in the working directory, and reads `setup.cfg` only when that table is missing. `pytest_add_cli_args_test_selection` is a list, and mutmut adds the deprecated `tests_dir` to it.
- `mutmut/__main__.py` (`run`) takes only mutant names and `--max-children`, so no pytest argument goes on the command line. `mutmut/runners/harness.py` (`PytestRunner._pytest_args_regular_run`, `list_all_tests`) gives `pytest_add_cli_args_test_selection` to pytest for the stats run and for the collection.
- A probe on a copy of the `pyproject.toml` of this repository showed that `_load_config()` returns the table entries followed by the added test module, that the other keys stay equal, and that the file holds its original bytes after the block.

## Existing Tool Considered
- The mutmut setting `pytest_add_cli_args_test_selection` carries the selection; no wrapper of mutmut is built.
- `tomlkit` (MIT, python-poetry, 0.15.2 released 2026-10-16) edits the TOML file and keeps its comments. The standard library `tomllib` only reads TOML. `toml` (0.10.2, last release 2020) is not maintained. `tomli-w` writes a whole file from a dict and removes the comments.

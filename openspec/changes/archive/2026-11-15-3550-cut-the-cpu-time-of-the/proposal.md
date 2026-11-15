# Proposal

## Why

The `startup-imports` row of `devops ci` (#3550) spends 57 to 71 s of child CPU time over its fresh interpreters, over the 38 s goal that #2369 set, and it reports the cost without cutting it. A start pays the dry-run models, the version record and the message and error catalogs before it runs a command. The change loads those on first use, so the fixed cost of a probe falls, and the row prints the CPU time of each probe so the cost split is visible.

## What Changes

- Load the names of `src/devops_cli/dry_run/__init__.py` on first use, so `import devops_cli.entry` loads no pydantic.
- Build the version record of `src/devops_cli/config/metadata.py` from `dataclasses`, so a start that reads the version loads no pydantic.
- Load the message and error catalogs on first use in `src/devops_cli/lang/__init__.py` and `src/devops_cli/lang/en/__init__.py`, so a start builds the help catalog alone.
- Report the child CPU time of each probe in `tests/gate/startup_imports.py`, so the cost split of the row is visible.
- Add a probe to `tests/gate/startup_imports.py` that fails when the root help leaves pydantic loaded.
- Name the new probe and the CPU line in `tests/commands/test_cli_startup_imports.py`.
- Edit `docs/TESTING.md` so its sentence on the row names the pydantic rule of the root help.
- The change carries a spec delta on `ci-gate-rows`, because the row is a `devops ci` row and the imports of a CLI start are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: A CLI start loads no pydantic and only the help catalog, The startup-import row keeps its budgets and its control

## Impact

- Code: `src/devops_cli/dry_run/__init__.py`, `src/devops_cli/config/metadata.py`, `src/devops_cli/lang/__init__.py`, `src/devops_cli/lang/en/__init__.py`
- Documents: `docs/TESTING.md`
- Tests: `tests/dry_run/test_dry_run_state.py`, `tests/config/test_metadata.py`, `tests/roadmap/stores/test_listing_snapshot.py`, `tests/lang/test_language_catalogs.py`, `tests/gate/startup_imports.py`, `tests/commands/test_cli_startup_imports.py`

## Feasibility

- Premise: the row is a file of the staging commit. `probes` answers "The path `tests/gate/startup_imports.py` is a file of the staging commit.", and it answers for the two module names "The path `devops_cli.main` is no file of the staging commit. No commit in the history deleted or renamed it." A module name is no path, and `read_file` on `src/devops_cli/entry.py` showed that file, as the context holds the code of `src/devops_cli/main.py`.
- The finding on the scenario is corrected and the correction is checked in the code: `src/devops_cli/roadmap/stage/stage_change.py:def _scenario_problem` judges only a scenario that names a code span, and it exempts a scenario that names none when the base spec holds its name. `read_spec` on `ci-gate-rows` showed that the base requirement `The startup-import row keeps its budgets and its control` holds the scenario `The control`, so the scenario now says "the root help runs after an import of a heavy package" and names no code span. The control imports `pydantic_ai` at `tests/gate/startup_imports.py:def _control_probe`, and the scenario states that as a heavy package.
- The review finding on the cost is right and the plan claims no cut of the command help: `src/devops_cli/commands/ci.py:22:from pydantic import BaseModel, ConfigDict, Field` and `src/devops_cli/commands/ci.py:68:from devops_cli.lang import HELP, MESSAGES` show that a command help probe imports its command module, which loads pydantic and the message catalog itself, so a cut of the shared start does not reach those probes. `search_code` on `from devops_cli.lang import` returned the same binding in `src/devops_cli/commands/ai.py:66:from devops_cli.lang import HELP, MESSAGES` and further command modules.
- The 38 s target is therefore not reachable by a cut of one import, and the plan asserts no CPU figure. From the issue's own split, a probe costs about 1 s and `import devops_cli.entry` is 0.25 to 0.36 s of it: 55 probes at 0.25 s is about 14 s, short of the 19 to 33 s that the goal needs, because the rest is the import of each command module. The plan cuts what the code shows is shared and gives the measurement to a person.
- The dry-run package is the pydantic import of the entry point: `src/devops_cli/entry.py:17:from devops_cli.dry_run.state import ( # noqa: E402` runs `src/devops_cli/dry_run/__init__.py`, and `src/devops_cli/dry_run/__init__.py:11:from devops_cli.dry_run.models import CommandDryRunResult` loads pydantic. Group 1 loads that name on first use.
- The version record is the pydantic import of `devops_cli.main`: `src/devops_cli/main.py:14:from devops_cli import __version__` reads `src/devops_cli/__init__.py:18:def __getattr__(name: str) -> Any:`, which imports `src/devops_cli/config/metadata.py`, and `src/devops_cli/config/metadata.py:12:from pydantic import BaseModel, ConfigDict` makes that a pydantic import. `read_file` on that file also showed `src/devops_cli/config/metadata.py:20:model_config = ConfigDict(frozen=True)`. Group 2 builds the record from `dataclasses`.
- The catalogs are the other import of `devops_cli.main`: `src/devops_cli/lang/__init__.py:5:from devops_cli.lang.en import (` runs `src/devops_cli/lang/en/__init__.py:7:from devops_cli.lang.en.messages import MESSAGES, LanguageCatalog`, so the help, message and error catalogs all build at a start. Group 3 loads the message and error names on first use with the module `__getattr__` that `src/devops_cli/__init__.py:18:def __getattr__(name: str) -> Any:` already shows in this repository.
- The module `__getattr__` keeps the catalog objects real: `tests/lang/test_language_catalogs.py:10:assert isinstance(MESSAGES, LanguageCatalog)` passes, because `from devops_cli.lang import MESSAGES` returns the object of the catalog module. A lazy proxy object was rejected for this reason.
- The four limits that the plan keeps, from `tests/gate/startup_imports.py`: `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_MAIN_AND_VERSION: int = 550`, `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_MAIN_AND_VERSION: int = 75`, `DEFAULT_STARTUP_IMPORT_MODULE_LIMIT_COMMAND_HELP: int = 1100`, `DEFAULT_STARTUP_IMPORT_DEVOPS_MODULE_LIMIT_COMMAND_HELP: int = 250`, and `_MAX_PARALLEL_PROBES: Final = 4`.
- The row keeps its control and its flag: `tests/gate/startup_imports.py:def control_problems` and `tests/gate/startup_imports.py:def probe_startup_imports` keep the `-X importtime` argument list and the child CPU report, and group 4 adds no bound in seconds, because `docs/TESTING.md:154:never on seconds. Each argv starts one fresh interpreter` holds the row to module counts.
- Group 4 edits no line of `tests/gate/startup_imports.py:def help_argvs` and of `BUDGETS_BY_ARGV`, so the help probes and their budgets stay as they are, and it adds one probe of the root help to `SCRIPT_PROBES`.
- Preconditions: no function that the plan calls needs a checkout of the repository, a client of a service or a network. `help_argvs`, `probe_startup_imports`, `control_problems` and `script_problems` take plain arguments, and each new case starts one local `python` child with `PYTHONPATH` set from `tests/support/paths.py`.
- Runner capabilities: the verify commands are `uv run devops ci test`, which runs `pytest`, and `uv run devops ci startup-imports` and `uv run devops ci docs`, which run `python` and `pytest`. All three are in the image and no `NOT_IN_RUNNER` tool applies. The pod settings `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` apply. The failure classes are `test` for a failing case and `lint` or `types` for a changed module.
- The registry is already lazy, so the cut of the refine block is no cut: `read_file` on `src/devops_cli/core/cli.py` showed `src/devops_cli/core/cli.py:245:if isinstance(typer_instance, str):`, which registers a `module:app` string and imports no command module for the root help.
- Not checked: this run starts no interpreter, so the guard's expected value and the CPU figures of the row are claims that the implementation settles. First check on the real system: `uv run devops ci startup-imports` three times on one host, reading the child CPU time that each run prints against the 38 s of the acceptance criterion.
- First check of the guard: `uv run devops ci startup-imports` names the new root-help probe as passed, and `uv run devops ci test tests/commands/test_cli_startup_imports.py` names it when the root help leaves `pydantic` loaded.
- First check of each cut: `uv run devops ci test tests/dry_run/test_dry_run_state.py`, `uv run devops ci test tests/config/test_metadata.py tests/roadmap/stores/test_listing_snapshot.py` and `uv run devops ci test tests/lang/test_language_catalogs.py`.

## Existing Tool Considered

`python -X importtime` and the `startup-imports` row of `devops ci` measure the cost of a start, and no open, maintained tool removes the imports of this CLI, so the change adopts no tool and builds none.

## Dependencies

None.

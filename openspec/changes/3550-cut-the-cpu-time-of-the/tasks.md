# Tasks

## 1. Load the dry-run names on first use

Kind: behavior. Reads: `src/devops_cli/dry_run/__init__.py`, `src/devops_cli/dry_run/state.py`, `src/devops_cli/dry_run/models.py`, `src/devops_cli/__init__.py`, `tests/dry_run/test_dry_run_state.py`. Changes: `src/devops_cli/dry_run/__init__.py`, `tests/dry_run/test_dry_run_state.py`.

- [x] 1.1 `test_a_start_that_imports_the_dry_run_state_loads_no_pydantic` in `tests/dry_run/test_dry_run_state.py`, which is the scenario `A start that imports the dry-run state`: on the base a fresh interpreter that imports `devops_cli.dry_run.state` prints that `devops_cli.dry_run.models` and `pydantic` are in `sys.modules`, so the case fails
  - Verification: `$ uv run devops ci test tests/dry_run/test_dry_run_state.py` fails on the base
- [x] 1.2 Replace the eager imports of `src/devops_cli/dry_run/__init__.py` with `__all__` and a module `__getattr__` that maps each name of `tests/dry_run/test_dry_run_state.py:10:from devops_cli.dry_run import (` to the module that holds it, in the shape of `src/devops_cli/__init__.py:18:def __getattr__(name: str) -> Any:`, so `src/devops_cli/entry.py` loads `state` alone and no pydantic; add the case to `tests/dry_run/test_dry_run_state.py`, which starts one `python` child with `PYTHONPATH` from `tests/support/paths.py`, asserts that `pydantic` and `devops_cli.dry_run.models` are absent, and asserts that each name of `__all__` resolves
  - Verification: `$ uv run devops ci test tests/dry_run/test_dry_run_state.py` passes

## 2. Build the version record without pydantic

Kind: behavior. Reads: `src/devops_cli/config/metadata.py`, `src/devops_cli/__init__.py`, `tests/config/test_metadata.py`, `tests/roadmap/stores/test_listing_snapshot.py`. Changes: `src/devops_cli/config/metadata.py`, `tests/config/test_metadata.py`, `tests/roadmap/stores/test_listing_snapshot.py`.

- [x] 2.1 `test_a_start_that_reads_the_version_loads_no_pydantic` in `tests/config/test_metadata.py`, which is the scenario `A start that imports the CLI main`: on the base a fresh interpreter that imports `devops_cli.main` prints that `pydantic` is in `sys.modules` through `devops_cli.config.metadata`, so the case fails
  - Verification: `$ uv run devops ci test tests/config/test_metadata.py tests/roadmap/stores/test_listing_snapshot.py` fails on the base
- [x] 2.2 Replace the pydantic model of `src/devops_cli/config/metadata.py` with a `@dataclass(frozen=True)` record and drop `src/devops_cli/config/metadata.py:12:from pydantic import BaseModel, ConfigDict`, keeping the fields and `_DEFAULT_METADATA`; replace `tests/roadmap/stores/test_listing_snapshot.py:170:return real.model_copy(update={"version": version})` with `dataclasses.replace`; add the case to `tests/config/test_metadata.py`, which starts one `python` child and asserts that `pydantic` is not in its modules after `import devops_cli.main`
  - Verification: `$ uv run devops ci test tests/config/test_metadata.py tests/roadmap/stores/test_listing_snapshot.py` passes

## 3. Build the help catalog alone at start

Kind: behavior. Reads: `src/devops_cli/lang/__init__.py`, `src/devops_cli/lang/en/__init__.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `tests/lang/test_language_catalogs.py`. Changes: `src/devops_cli/lang/__init__.py`, `src/devops_cli/lang/en/__init__.py`, `tests/lang/test_language_catalogs.py`.

- [x] 3.1 `test_a_start_that_imports_the_cli_main_loads_the_help_catalog_alone` in `tests/lang/test_language_catalogs.py`, which is the scenario `A start that builds the help catalog`: on the base a fresh interpreter that imports `devops_cli.main` prints that `devops_cli.lang.en.messages` and `devops_cli.lang.en.errors` are in `sys.modules`, so the case fails
  - Verification: `$ uv run devops ci test tests/lang/test_language_catalogs.py` fails on the base
- [x] 3.2 Replace the eager imports of `src/devops_cli/lang/__init__.py` and `src/devops_cli/lang/en/__init__.py` with `__all__` and a module `__getattr__` in each, so `from devops_cli.lang import HELP` builds `devops_cli.lang.en.help` alone and `MESSAGES` and `ERRORS` load on first access; keep `tests/lang/test_language_catalogs.py:5:from devops_cli.lang import ERRORS, HELP, MESSAGES, ErrorCatalog, HelpCatalog, LanguageCatalog` passing, so `tests/lang/test_language_catalogs.py:10:assert isinstance(MESSAGES, LanguageCatalog)` still holds; add the case to that module, which starts one `python` child and asserts the three module names
  - Verification: `$ uv run devops ci test tests/lang/test_language_catalogs.py` passes

## 4. Report each probe's CPU and refuse pydantic in the root help

Kind: other. Reads: `tests/gate/startup_imports.py`, `tests/commands/test_cli_startup_imports.py`, `src/devops_cli/entry.py`, `docs/TESTING.md`. Changes: `tests/gate/startup_imports.py`, `tests/commands/test_cli_startup_imports.py`.

- [x] 4.1 In `tests/gate/startup_imports.py`, print the child's own `resource.getrusage(resource.RUSAGE_SELF)` user plus system time on a marked line of `_STARTUP_PROBE`, read it in `read_startup_imports` into a new `cpu_seconds` field of `StartupImports`, and print one line per probe in `main` beside the total; add a `ScriptProbe` whose code runs `devops_cli.entry.main(["--help"])` and prints whether `pydantic` is in `sys.modules`, with `False` as its expected value, placed before the banner probe whose expected value is `1`; keep `tests/gate/startup_imports.py:def help_argvs`, `BUDGETS_BY_ARGV`, `CONST_CLI_HEAVY_MODULES`, the four limits and the `-X importtime` argument list. In `tests/commands/test_cli_startup_imports.py`, feed the new marked line in the case that reads a probe output, take the banner probe by its expected value in place of `tests/commands/test_cli_startup_imports.py:188:probe = SCRIPT_PROBES[-1]`, and add a case that gives the new root-help probe `__R__true` and asserts that `script_problems` names it
  - Verification: `$ uv run devops ci test tests/commands/test_cli_startup_imports.py` passes

## 5. Name the pydantic rule of the row in the testing guide

Kind: other. Reads: `docs/TESTING.md`, `tests/gate/startup_imports.py`. Changes: `docs/TESTING.md`.

- [x] 5.1 Edit the sentence on the `startup-imports` row of `docs/TESTING.md` so it says that the row fails when the root help leaves `pydantic` loaded and that it prints the child CPU time of each probe
  - Verification: `$ uv run devops ci docs` passes
- [x] 5.2 Edit `docs/TESTING.md` so its sentence on the `startup-imports` row names the pydantic rule of the root help and the CPU line of each probe
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Pending person: The row `startup-imports` uses at most 38 s of CPU time (user plus system) over three runs on one host., Only a person can measure it. The row prints the child CPU time and asserts nothing about seconds (`docs/TESTING.md:154:never on seconds. Each argv starts one fresh interpreter`), and each command help probe still imports its command module, which loads pydantic and the message catalog, so no group asserts the 38 s figure.
- Group 4: The limits and the control are as before.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

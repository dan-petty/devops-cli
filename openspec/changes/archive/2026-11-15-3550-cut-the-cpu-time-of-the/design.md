# Design

## Decisions

- **Cut the imports that a probe pays before it runs a command, and keep every help probe.**: The fixed cost is paid by each fresh interpreter, so a cut there is paid by each probe, while a dropped probe loses the coverage of that command group.
- **Load the dry-run names on first use with a module `__getattr__`.**: `src/devops_cli/entry.py:17:from devops_cli.dry_run.state import ( # noqa: E402` runs the package `__init__`, whose pydantic models a start never reads, and `src/devops_cli/__init__.py:18:def __getattr__(name: str) -> Any:` is the pattern this repository already uses.
- **Build the version record of `src/devops_cli/config/metadata.py` from `dataclasses`.**: `src/devops_cli/main.py:14:from devops_cli import __version__` reads the version at the import of `main`, and `src/devops_cli/config/metadata.py:12:from pydantic import BaseModel, ConfigDict` makes that a pydantic import; the frozen record has three users.
- **Load the message and error catalogs on first use in `src/devops_cli/lang/__init__.py` and `src/devops_cli/lang/en/__init__.py`.**: A start builds all three catalogs at the import of `devops_cli.main`, and the help reads only the help catalog.
- **Report the child CPU time of each probe and add no bound in seconds.**: The issue asks where the cost is, and `docs/TESTING.md:154:never on seconds. Each argv starts one fresh interpreter` holds the row to module counts.
- **Guard the cut with a probe of the root help that expects no pydantic.**: The 550-module limit of the root help admits pydantic, so the limits alone do not catch its return.
- **State the control scenario as an import of a heavy package, and name no code span in it.**: The scenario is the one of the base spec, and `src/devops_cli/roadmap/stage/stage_change.py:def _scenario_problem` exempts a scenario that names no code span when the base spec holds its name, while a code span needs a behavior test that names it.
- **Give the 38 s criterion to a person.**: The row prints the child CPU time and asserts nothing about seconds, so only a person measures three runs on one host.

## Rejected alternatives

- **Reduce the number of help probes to reach the budget.**: `docs/TESTING.md:154:never on seconds. Each argv starts one fresh interpreter` states that the row fails on any heavy module that any command group's `--help` imports, and the module-count budget is read from one argv, so a sampled set hides a regression in an untested help.
- **Fail the row when its child CPU time is above 38 s.**: `docs/TESTING.md:154:never on seconds. Each argv starts one fresh interpreter` states that the row never fails on time, and a bound in seconds follows the speed of the host.
- **Make `MESSAGES` a lazy proxy object that loads the catalog on first attribute access.**: `tests/lang/test_language_catalogs.py:10:assert isinstance(MESSAGES, LanguageCatalog)` reads the real catalog object, so a proxy breaks that case.
- **Add `pydantic` to `CONST_CLI_HEAVY_MODULES`.**: `src/devops_cli/commands/ci.py:22:from pydantic import BaseModel, ConfigDict, Field` loads pydantic in the script probe that imports `devops_cli.commands.ci` and asserts that no heavy module is loaded, so that probe would fail.
- **Make the command registry of `src/devops_cli/main.py` lazy.**: `src/devops_cli/core/cli.py:245:if isinstance(typer_instance, str):` registers each command as a `module:app` string, so the root help already imports no command module.
- **Run the help of every command group in one interpreter.**: `tests/gate/startup_imports.py:def probe_startup_imports` starts one fresh interpreter per argv, because a module that one argv imports stays in `sys.modules` and would hide the import of the next.

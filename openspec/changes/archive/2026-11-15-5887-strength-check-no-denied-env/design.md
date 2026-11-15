# Design

## Decisions
- **The selection goes in the mutmut table, for the run only.** `_mutmut_test_selection` reads `pyproject.toml` with tomlkit, sets `pytest_add_cli_args_test_selection` of `[tool.mutmut]` to the entries of the table followed by the scoped test modules, and writes the file. A `finally` writes the original bytes back, or removes the file when the checkout had none. The block holds only `mutmut run`: `mutmut results` reads the results of the run and no test selection. The job commits after the block ends, so no commit holds the changed file. Each test module is one entry of the array, so a path with a space stays one argument.
- **No tests, no edit.** With no scoped test module, the file stays as it is and mutmut runs the selection of the table, as before.
- **A refused command is `refused_tool`.** `_failure_class_of` in `implement_run.py` gives `refused_tool` for a `SecurityError`. The process runner raises it before the child starts, so a new runner image meets the same refusal. The class has the action `wait`, and the rule `digest` clears only a class with the action `retry`. The class exists, so no counter, dashboard or table of classes changes. `CLASS_BY_EXCEPTION` of `failure.py` stays as it is: the stage job and the other jobs use that map, and this item changes only the implement job.

## Rejected alternatives
- **An exception for `PYTEST_ADDOPTS` in the env check.** The key is a security control (#2747): `--junitxml=<path>` makes pytest write a file at a path that the caller names. The issue forbids an exception.
- **More arguments for `mutmut run`.** The `run` command of mutmut 3.8.1 takes only mutant names and `--max-children` (`mutmut/__main__.py`).
- **A `setup.cfg` section.** mutmut reads `setup.cfg` only when `pyproject.toml` has no `[tool.mutmut]`, and this repository has one.
- **The key `tests_dir`.** mutmut 3.8.1 warns that the key is deprecated and names `pytest_add_cli_args_test_selection` instead (`mutmut/configuration.py`).
- **A text edit of the TOML file.** The array of this repository has many lines and holds comments; a text edit of TOML that we write is a parser of our own.
- **A launcher that changes the config object of mutmut in memory.** It depends on the private state of mutmut (`mutmut.configuration._config`), and a forkserver worker reads the file again.
- **`plan_defect` for a refused command.** The plan is not at fault: an amended plan meets the same refusal.
- **A new failure class.** `refused_tool` already means a command that a policy refused, with the action `wait`, and a new class needs a change of the counters and the dashboards.

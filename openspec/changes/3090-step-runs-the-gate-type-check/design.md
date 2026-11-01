# Design

## Decisions

- **One module defines the type check of the gate.** `src/devops_cli/ci/typecheck.py` holds `TYPECHECK_PATHS` (`("src",)`), `TYPECHECK_OPTIONS` (`--python-version`, the project Python version, `--strict`), `typecheck_argv(targets)` and `typecheck_files(changed)`. The row `typecheck` of `get_check_specs` calls `typecheck_argv(TYPECHECK_PATHS)`, and its command line stays as it is. The step calls `typecheck_argv` with `--` and the files of `typecheck_files`. A change of the gate, such as a new path, changes the step.
- **Keep the module out of `commands/ci.py`.** The step must not import a Typer command module. The `ci` package already holds the gate helpers (`fail_to_pass`, `cache`), and `config.defaults` and `config.commands` hold the constants that the module needs.
- **A path test, not a glob.** `typecheck_files` keeps a changed `.py` path when `PurePosixPath(path).is_relative_to(root)` holds for one root of `TYPECHECK_PATHS`. Git gives the paths relative to the checkout with `/`, so no normalisation is needed.
- **No `mypy` run when the file set is empty.** A step that changes only test files runs `ruff check` and `ruff format` and no `mypy`. Mypy with no file would check the whole project, or fail.
- **`ruff` stays on every changed file.** The pre-commit hooks run `ruff-check` and `ruff-format` on every staged Python file, so the step does the same. A lint error in a test file that the agent changed is its own error.
- **The step passes the options of the gate.** The step now passes `--python-version 3.14` too. The `pyproject.toml` sets the same value, so the result does not change, and the command line equals the one of the gate.

## Rejected alternatives

- **A baseline of the old errors in `tests/`.** The gate has no baseline. The 741 errors would be a list to keep, and it would grow stale at each merge. The issue asks for the rule of the gate, not a baseline.
- **Fix the 741 errors and type-check `tests/` in the gate.** The change would be many files, so it does not fit one reviewable pull request. It also makes the gate slower, and the gate has a limit of 5 minutes for a check. The issue does not ask for it. It is a decision for the owner.
- **Filter the output of mypy for the changed files.** Mypy reports errors of imported files, and a filter would be a parser of mypy output that needs a test. Giving mypy the right files needs no filter.
- **`MYPYPATH=src` or `mypy_path = "src"` for the runner.** The first version of the issue named a path problem. It removes only the `import-untyped` errors and leaves 10 real, old errors in the two files. See the issue.
- **A second list of paths in `implement_step.py`.** It is the drift that tracker #3027 forbids. The drift test would only catch it after the fact.

# Proposal: #6815

## Why

The error catalog `docs/ERRORS.md` had no row for the four `DevOpsCLIError` subclasses of `devops_cli.github.onboard` (#6815). `DocGenerator._import_all_exception_modules` imports only the modules of `devops_cli.exceptions` and of `CONST_DOMAIN_EXCEPTION_MODULES`, a list that a person keeps. #6806 added the onboard modules and did not add them to the list, and no check failed. The catalog test saw the onboard errors only when an earlier test of the same worker imported them, so its result changed with the shard layout. The change of #3244 then added the two modules to the list. The next module with an error class can miss the list again, and no check fails.

## What Changes

- The generator imports the module of each `.py` file under the `devops_cli` package before it reads the `DevOpsCLIError` subclasses. So the catalog lists every error class, and a new module needs no list entry.
- `CONST_DOMAIN_EXCEPTION_MODULES` goes, with its import in `src/devops_cli/docs/generator.py`, its only reader.
- A new test runs the import step of the generator in a fresh interpreter. It fails when a module of a `.py` file of the package is not loaded after that step, and names the error classes that such a module adds.
- `uv run devops docs generate` keeps the rows of `AnswerFlagError`, `BaselineUnreadableError`, `RouteRefusedError` and `RouteWriteError` in `docs/ERRORS.md`, and the file does not change.
- The content of `docs/ERRORS.md` is observable output of `devops docs generate`, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `docs-error-catalog`: The error catalog lists every error class of devops-cli

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/docs/generator.py`, `src/devops_cli/config/constants.py`
- Documents: none. `docs/ERRORS.md` does not change.
- Tests: `tests/docs/test_exceptions.py`
- `devops docs generate` imports about 400 more modules and takes about 2.3 s more on a workstation (design decision 3).

## Feasibility

- On 676e10721, `uv run pytest -n 0 tests/docs/test_exceptions.py::test_each_error_class_declares_the_codes_of_its_catalog_row` gives `1 passed`. With `tests/github/onboard/test_onboard_routes.py` first in the same process, it gives `1 failed, 35 passed` and `Left contains 4 more items`.
- A scratch script that imports each module that `pkgutil.walk_packages` gives (957 modules, no import failure) finds four error classes that the generator does not load: `AnswerFlagError` and `BaselineUnreadableError` of `devops_cli.github.onboard.baseline`, and `RouteRefusedError` and `RouteWriteError` of `devops_cli.github.onboard.routes`.
- The package holds 964 `.py` files. `pkgutil.walk_packages` does not give the 6 modules of `devops_cli.docker`, a directory with no `__init__.py` (a namespace package). The file list gives all 964, and each one imports with no failure.
- When the catalog runs in `devops docs generate`, 565 modules of devops-cli are loaded. An import of all 964 adds 2.4 s to 2.5 s in a scratch script (two runs).
- In a fresh interpreter, the import step of the generator leaves 221 modules of the package unloaded on 676e10721, and their import adds the four onboard classes. On ec5b16bdc, after #3244, it leaves 218 modules unloaded, and their import adds no error class.
- The rows of the four onboard errors are in `docs/ERRORS.md` on ec5b16bdc. The cause, the hand list with no check, is still there, so the rest of the issue can be built as written.

## Existing Tool Considered

The standard library covers the need: `pathlib.Path.rglob` gives the source files, `devops_cli.core.import_graph.module_name` gives the dotted name of each file, `importlib.import_module` loads it, and `type.__subclasses__` gives each error class. No third-party tool is necessary. `pkgutil.walk_packages` was considered and rejected (design). The change deletes `CONST_DOMAIN_EXCEPTION_MODULES` and the `pkgutil.iter_modules` loop of the generator. It builds about 10 lines of code and 40 lines of test: 20k tokens and 1 hour.

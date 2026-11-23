# Tasks

## 1. The generator imports every module of devops-cli

Kind: behavior. Reads: `src/devops_cli/docs/generator.py`, `src/devops_cli/core/import_graph.py`, `src/devops_cli/config/constants.py`, `tests/docs/test_exceptions.py`, `tests/docs/test_docs.py`, `tests/ai/agents/test_pydantic_ai_exceptions.py`. Changes: `src/devops_cli/docs/generator.py`, `src/devops_cli/config/constants.py`, `tests/docs/test_exceptions.py`.

- [ ] 1.1 Write `test_the_error_catalog_imports_the_module_of_each_source_file` in `tests/docs/test_exceptions.py`. It runs a fresh interpreter that calls `DocGenerator._import_all_exception_modules`, then imports the module of each `.py` file of the package that is not loaded, and prints those modules and the `DevOpsCLIError` subclasses that they added. The test expects neither. On the base, the child prints 218 modules
  - Verification: `$ uv run devops ci test tests/docs/test_exceptions.py` fails on the base
- [ ] 1.2 In `src/devops_cli/docs/generator.py`, make `_import_all_exception_modules` import the module of each `.py` file under the directory of the `devops_cli` package, with `module_name` of `devops_cli.core.import_graph`, and remove the `pkgutil.iter_modules` loop. Remove `CONST_DOMAIN_EXCEPTION_MODULES` from `src/devops_cli/config/constants.py` and from the imports of the generator. Run `uv run devops docs generate`: `docs/ERRORS.md` keeps the four onboard rows and does not change
  - Verification: `$ uv run devops ci test tests/docs/test_exceptions.py tests/docs/test_docs.py tests/ai/agents/test_pydantic_ai_exceptions.py` passes, and `$ uv run devops ci --check --only docs` passes

## Criteria

- Group 1: Test first: a check fails when a module of `src/devops_cli` defines a `DevOpsCLIError` subclass and the generator does not import that module. The check fails on the base, and `docs/ERRORS.md` keeps the rows of the four onboard errors. The catalog test passes alone and after `tests/github/onboard/test_onboard_routes.py` in one process.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

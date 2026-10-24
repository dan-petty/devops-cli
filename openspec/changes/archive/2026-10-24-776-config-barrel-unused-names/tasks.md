# Tasks

## 1. Failing tests for import isolation and init invariants

- [x] 1.1 Add failing test in `tests/test_code_metrics.py` asserting that `python -m devops_cli.core.code_metrics` in a fresh subprocess loads neither `pydantic`, `typer`, nor `devops_cli.config`.
- [x] 1.2 Extend `tests/test_architectural_invariants.py` to assert that `src/devops_cli/config/__init__.py` and `src/devops_cli/core/__init__.py` contain only a docstring.
- [x] 1.3 Extend `tests/test_cli_startup_imports.py` to assert that `src/devops_cli/__init__.py` assigns `PYDANTIC_DISABLE_PLUGINS` before any import.

## 2. Package initializers cleanup

- [x] 2.1 Replace `src/devops_cli/config/__init__.py` content with only a module docstring.
- [x] 2.2 Replace `src/devops_cli/core/__init__.py` content with only a module docstring.
- [x] 2.3 Refactor `src/devops_cli/__init__.py` to remove module-level `devops_cli` imports, serving `__version__` lazily through `__getattr__`.
- [x] 2.4 Remove `test_config_package_exports_resolve` from `tests/test_public_export_surface.py` and `test_core_getattr_exports` from `tests/test_fast_dispatch.py`.

## 3. Importer redirection

- [x] 3.1 Point source importers in `argo`, `commands`, `sandbox`, `docker`, and `ai` directly at defining config modules.
- [x] 3.2 Point test importers in `tests/test_metadata.py`, `tests/test_argo_fleet.py`, `tests/test_data_dir_configuration.py`, `tests/test_verdict_polarity.py`, `tests/test_server_service.py`, and `tests/test_tools_lock.py` at defining modules.

## 4. Unused names deletion and test-only names relocation

- [x] 4.1 Delete 68 unused constants from `src/devops_cli/config/constants.py`, preserving `CONST_ERROR_CODE_HARNESS` and `CONST_ERROR_CODE_STRUCTURED_VALIDATION`.
- [x] 4.2 Delete 94 unused defaults from `src/devops_cli/config/defaults.py`.
- [x] 4.3 Move test-only constants and defaults into their consuming test modules or test support helpers and update references.

## 5. Verification and documentation

- [x] 5.1 Run test suite and check all criteria pass (`uv run devops ci test`).
- [x] 5.2 Validate docs and update generated references (`uv run devops docs check`).
- [x] 5.3 Validate OpenSpec change integrity (`uv run devops openspec check`).

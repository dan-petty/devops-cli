# Proposal

## Why

Issue #776: The config barrel in `src/devops_cli/config/__init__.py` re-exports hundreds of names. Only 27 names are imported through it. Furthermore, eager package imports in `src/devops_cli/__init__.py` and `src/devops_cli/core/__init__.py` load `pydantic`, `typer`, and `devops_cli.config` into memory. This eager loading bloats startup time and leaks internal dependencies into tools such as `devops_cli.core.code_metrics`.

## What Changes

- Clear `src/devops_cli/config/__init__.py` so it contains only a docstring.
- Clear `src/devops_cli/core/__init__.py` so it contains only a docstring.
- Update `src/devops_cli/__init__.py` to import nothing at module level and resolve `__version__` lazily via `__getattr__`.
- Keep the `PYDANTIC_DISABLE_PLUGINS` assignment at the top of `src/devops_cli/__init__.py`.
- Point all source and test modules importing from the config barrel directly at defining modules.
- Delete unused constants and defaults from `src/devops_cli/config/constants.py` and `src/devops_cli/config/defaults.py`.
- Move test-only constants and defaults into the tests that use them or into test support modules.
- Remove `test_config_package_exports_resolve` from `tests/test_public_export_surface.py`.
- Remove `test_core_getattr_exports` from `tests/test_fast_dispatch.py`.
- Add test coverage asserting that `src/devops_cli/config/__init__.py` and `src/devops_cli/core/__init__.py` hold only docstrings.
- Add test coverage verifying that `devops_cli.core.code_metrics` in a fresh subprocess loads neither `pydantic`, `typer`, nor `devops_cli.config`.
- Extend AST startup ordering checks to cover `src/devops_cli/__init__.py`.

This change alters no behavior that a consumer observes outside internal import performance. The change sets `skip_specs: true` in `.openspec.yaml`.

This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/__init__.py`: Remove module-level imports and serve `__version__` through `__getattr__`.
- `src/devops_cli/config/__init__.py`: Delete all imports and exports, leaving only a module docstring.
- `src/devops_cli/core/__init__.py`: Delete all exports, leaving only a module docstring.
- `src/devops_cli/config/constants.py`: Remove unused constants and test-only constants.
- `src/devops_cli/config/defaults.py`: Remove unused defaults and test-only defaults.
- Importer modules under `src/devops_cli/` and `tests/`: Redirect imports to defining modules.
- `tests/test_architectural_invariants.py`: Enforce docstring-only invariants on `config` and `core` package inits.
- `tests/test_code_metrics.py`: Add test verifying subprocess import isolation.
- `tests/test_cli_startup_imports.py`: Verify AST assignment ordering in `src/devops_cli/__init__.py`.

## Feasibility

I confirmed the premise against the real system:

- Executed `python3 -c "import devops_cli.core.code_metrics, sys; ..."` in a fresh subprocess. The command loaded 74 modules across `pydantic`, `typer`, and `devops_cli.config`.
- Audited `src/devops_cli/config/__init__.py` (775 lines) and `src/devops_cli/core/__init__.py` (90 lines). Both contain barrels and eager imports that can be removed.
- Analyzed all symbols in `constants.py` and `defaults.py` with an AST script. Found 68 unread constants, 94 unread defaults, 50 test-only constants, and 8 test-only defaults.
- Verified that `CONST_ERROR_CODE_HARNESS` and `CONST_ERROR_CODE_STRUCTURED_VALIDATION` remain reserved for #1006.
- Confirmed that `docs/agent/tasks/` was decommissioned in commit 5787ea72 (#2041), so Criterion 7 regarding task-773 is already obsolete.
- Verified that `.pre-commit-config.yaml` lines 52-58 invoke `python3 -P src/devops_cli/core/code_metrics.py` without referring to init bloat.

## Existing Tool Considered

Standard Python import mechanisms and Python 3.7+ module `__getattr__` are standard language features. No third-party dependency is required.

# Design

## Context

See `proposal.md`. The configuration package exposes a monolithic re-export barrel in `src/devops_cli/config/__init__.py`. The package inits in `src/devops_cli/__init__.py` and `src/devops_cli/core/__init__.py` perform eager imports. These imports force modules such as `devops_cli.core.code_metrics` to load `pydantic`, `typer`, and `devops_cli.config`. In addition, `constants.py` and `defaults.py` accumulate unreferenced definitions and test-only definitions.

## Goals / Non-Goals

**Goals:**
- Eliminate the config re-export barrel in `src/devops_cli/config/__init__.py`.
- Eliminate eager re-exports in `src/devops_cli/core/__init__.py`.
- Make `src/devops_cli/__init__.py` import nothing at module level while resolving `__version__` through `__getattr__`.
- Keep the `PYDANTIC_DISABLE_PLUGINS` assignment at the top of `src/devops_cli/__init__.py`.
- Point all modules that import from the barrel to their defining modules.
- Remove all unreferenced names from `src/devops_cli/config/constants.py` and `src/devops_cli/config/defaults.py`.
- Keep `CONST_ERROR_CODE_HARNESS` and `CONST_ERROR_CODE_STRUCTURED_VALIDATION` for #1006.
- Relocate test-only constants and defaults to test files or test fixtures.
- Add invariant tests ensuring `config/__init__.py` and `core/__init__.py` remain docstring-only.
- Add integration tests ensuring `code_metrics` in a fresh subprocess loads neither `pydantic`, `typer`, nor `devops_cli.config`.

**Non-Goals:**
- Moving single-consumer configuration values to their feature packages (handled in #1025-#1032).
- Modifying `CONST_ERROR_CODE_*` names reserved for #1006.

## Decisions

### Decision 1: Docstring-only package inits for `config` and `core`
- **Rationale**: Empty package initializers prevent eager dependency cascades when importing specific submodules.
- **Rejected alternative**: Lazy exports with `__getattr__` dictionaries. Rejected because no product code needs to import names directly from `config` or `core` packages.

### Decision 2: Lazy version resolution in `src/devops_cli/__init__.py`
- **Rationale**: Dynamic resolution in `__getattr__` prevents loading `config.metadata` and `pydantic` at package load time. The `__version__: str` annotation preserves static metadata analysis.
- **Rejected alternative**: Hardcoding version strings. Rejected because `devops_cli` derives version strings from `pyproject.toml` metadata dynamically.

### Decision 3: Move test-only constants to test modules
- **Rationale**: Production configuration modules should contain only production settings. Moving test invariants to test files isolates test logic from the shipping package.
- **Rejected alternative**: Keeping test constants in `config/constants.py`. Rejected because production code must not carry test scaffolding.

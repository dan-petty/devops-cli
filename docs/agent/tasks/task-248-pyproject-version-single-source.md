# Task 248: Use pyproject.toml as Single Source of Truth for Version

**Issue**: [#248](https://github.com/dan-petty/devops-cli/issues/248)
**Status**: Done
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`, `scope/config`

---

## 1. Description & Objectives

The application version was duplicated in multiple locations across the codebase, notably hardcoded as `__version__ = "0.2.20"` in `src/devops_cli/__init__.py`, `version="0.1.11"` in `src/devops_cli/config/metadata.py`, and `return "0.1.0"` in `src/devops_cli/telemetry/tracer.py`. This required synchronized manual edits or release automation rewriting across multiple files on every version increment, risking divergence.

This refactor establishes `pyproject.toml` as the single authoritative source of truth for the application version, with `src/devops_cli/__init__.py` dynamically loading the version via `devops_cli.config.metadata.get_version()`.

#### Key Deliverables:
1. **Dynamic Version Initialization ([`src/devops_cli/__init__.py`](file:///workspaces/devops-cli/src/devops_cli/__init__.py))**:
   - Initialize `__version__` from `get_version()` (derived from `pyproject.toml` with `load_project_metadata()`).
   - Maintain public API exports (`__version__`, `get_version`, etc.).
2. **Release Engine Compatibility ([`src/devops_cli/commands/release.py`](file:///workspaces/devops-cli/src/devops_cli/commands/release.py))**:
   - Ensure `_get_init_version` returns `pyproject.toml` version when `__init__.py` uses dynamic derivation.
   - Ensure `_update_init_version` detects dynamic derivation and returns `True` without modifying `__init__.py`.
   - Ensure `_update_pyproject_version` invalidates `load_project_metadata.cache_clear()` upon updating version.
3. **Clean Up Stale Version Fallbacks ([`src/devops_cli/config/metadata.py`](file:///workspaces/devops-cli/src/devops_cli/config/metadata.py), [`src/devops_cli/telemetry/tracer.py`](file:///workspaces/devops-cli/src/devops_cli/telemetry/tracer.py))**:
   - Update `_DEFAULT_METADATA.version` in `metadata.py` to `"0.0.0"`.
   - Update fallback in `tracer.py` to `"0.0.0"`.
4. **Test Suite Standardization ([`tests/test_instruction_generator.py`](file:///workspaces/devops-cli/tests/test_instruction_generator.py), [`tests/test_release.py`](file:///workspaces/devops-cli/tests/test_release.py))**:
   - Replace hardcoded `version="0.2.20"` in `test_instruction_generator.py` with `__version__`.
   - Add unit test verifying release commands properly handle dynamically versioned `__init__.py`.
5. **Quality & Architectural Invariant Gates**:
   - Strictly enforce cyclomatic complexity $\le 10$ and nesting depth $\le 5$.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).

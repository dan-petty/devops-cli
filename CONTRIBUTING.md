# Contributing to DevOps CLI

Thank you for your interest in contributing to DevOps CLI! This document outlines our engineering standards, development workflow, and pull request governance.

---

## 1. Development Philosophy & Core Invariants

DevOps CLI follows an uncompromising quality-first, test-driven engineering culture defined in [`AGENTS.md`](AGENTS.md):

- **Test-First Implementation (TDD)**: All features, fixes, and refactorings **must** have tests written first. Tests serve as the executable documentation of public interfaces, edge cases, and architectural boundaries.
- **Strict Complexity & Nesting Caps**:
  - Cyclomatic complexity $\le 10$ across all functions and closures (`tests/test_architectural_invariants.py`).
  - Maximum nesting depth $\le 5$ (< 6 indentation levels) project-wide.
  - Decompose multi-step procedures into dedicated single-responsibility helpers and pure predicates.
- **Strongly Typed Domain Exceptions**:
  - All domain error states must raise strongly typed exceptions inheriting from `DevOpsCLIError` under `src/devops_cli/exceptions/`.
  - Raising bare Python built-in exceptions (`ValueError`, `RuntimeError`, `TypeError`) is strictly prohibited.
- **Minimum 90% Code Coverage**: Continuous quality gate enforced by `devops ci` across all `src/` modules.
- **Pre-1.0 Alpha Status & Zero Backwards Compatibility**: DevOps CLI is pre-1.0 alpha software. Until at least release `1.0.0`, there is no intention of maintaining backwards compatibility. The codebase must remain clean of legacy references and obsolete shims at all times so that it can reach maturity at a reasonable rate. Any version after `1.0.0` will follow strict semantic versioning conventions, and employ all change management best practices including feature flags, deprecations, and migration functionality.
- **Zero Zombie Code & Legacy Remnants**: Ruthlessly remove obsolete shims, legacy workarounds, and deprecated aliases. Never introduce compatibility shims during the pre-1.0 development cycle.

---

## 2. Local Environment Setup

We use modern Python 3.14+ runtime tooling powered by [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Clone repository
git clone https://github.com/dan-petty/devops-cli.git
cd devops-cli

# 2. Synchronize virtual environment and all dependency groups
uv sync --all-groups --all-extras

# 3. Install pre-commit hooks
uv run pre-commit install
```

---

## 3. Test-First Development Cycle (Inner Loop)

1. **Write Specification via Tests**:
   Author unit and integration tests in `tests/test_<feature>.py`.
   ```bash
   uv run pytest tests/test_<feature>.py
   ```
2. **Implement Feature Code**:
   Write concise, well-factored code in `src/devops_cli/` to satisfy the tests.
3. **Verify Fast Local Loop**:
   ```bash
   uv run ruff check path/to/modified.py
   uv run mypy path/to/modified.py
   uv run pytest tests/test_architectural_invariants.py
   ```
4. **Run Comprehensive CI Quality Gate**:
   Run the unified quality suite before committing:
   ```bash
   uv run devops ci
   ```
   Validates 10 gates concurrently: Python runtime, tests, 90% coverage, linting, formatting, strict typing, dependency audit, security scanning, workflow actionlint, and documentation freshness.

---

## 4. Git Hygiene & Branch Management

- **Branch Naming**: Use descriptive topic branch prefixes:
  - `feat/<short-description>`: New features
  - `fix/<short-description>`: Defect repairs
  - `refactor/<short-description>`: Code structure improvements
  - `docs/<short-description>`: Documentation changes
- **Branch Targeting**:
  - All feature, fix, refactoring, and docs branches **must target the active release branch** (e.g. `--base release/v0.2.11`), **NEVER** `main` directly.
  - Official release branches target `main` when cutting an official release tag.
- **Draft Pull Requests for In-Progress Work**:
  - Open pull requests as drafts (`gh pr create --draft`) whenever implementation is ongoing or not yet ready for final maintainer review and merge.
  - Convert to ready for review (`gh pr ready <pr-number>`) once all features, tests, and CI quality gates pass.
- **Conventional Commits**:
  All commits must strictly follow the Conventional Commits format:
  ```
  feat(k8s): add automated minikube helm adoption check
  fix(runner): prevent thread pool executor blocking on tool timeout
  docs(sdlc): add enterprise lifecycle manual
  ```
- **Documentation Synchronization**:
  Run documentation introspection after any command or option change:
  ```bash
  uv run devops docs generate --sync-readme
  ```

---

## 5. Routine Tasks Checklist

Before opening a pull request or handing off work, verify all applicable tasks from [`docs/ROUTINE_TASKS.md`](docs/ROUTINE_TASKS.md) have been completed.

# Task 115: Core Dependency Ecosystem Alignment & Lockfile Synchronization

**Issue**: [#115](https://github.com/dan-petty/devops-cli/issues/115)
**PR**: None
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p2-medium`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Perform scheduled alignment across core project dependencies (`typer`, `pydantic-ai`, `httpx2`, `ruff`, etc.) to prevent version drift, security vulnerabilities, and runtime deprecation warnings:
1. Verify compatibility of core dependencies against Python 3.14+ runtime.
2. Upgrade dependency lockfile via `uv lock --upgrade`.
3. Synchronize development virtual environment via `uv sync`.
4. Ensure zero breaking changes or regressions across all test suites and quality gates.

---

## 2. Planned Changes

1. **`uv.lock`**:
   - Upgrade package versions to latest compatible releases via `uv lock --upgrade`.
2. **`pyproject.toml`** (if needed):
   - Align minimum dependency bounds if newer features or bug fixes are required.
3. **`docs/agent/tasks/task-115-core-dependency-alignment.md`**:
   - Dedicated task tracking document.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#115) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-115-core-dependency-alignment.md`.
- [x] Checkout dedicated topic branch `chore/115-core-dependency-alignment`.
- [ ] Run `uv lock --upgrade` and `uv sync`.
- [ ] Verify test suite and quality gates pass cleanly.
- [ ] Commit with concise Conventional Commit message.
- [ ] Open Draft Pull Request targeting `release/v0.2.17`.
- [ ] Transition PR to ready, verify merge readiness, squash-merge into `release/v0.2.17`, and close issue #115.

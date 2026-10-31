# Design

## Context

See proposal.md for motivation and scope (#1325).
Tests for `ci`, `test`, `devcontainer`, `workspace`, `install-tools`, `uv`, `branches`, and `pipeline` frequently monkeypatch internal functions (`_get_project_root`, `_run`, `run_subprocess`, `_download`) and import private symbols. `src/devops_cli/commands/ci.py` contains 2,464 lines mixing CLI dispatch with gate caching, check definitions, coverage cleanup, and execution logic, and contains branches checking `os.getenv("PYTEST_CURRENT_TEST")`.

## Goals / Non-Goals

**Goals:**
- Eliminate `PYTEST_CURRENT_TEST` detection in `commands/ci.py` and `core/process.py`.
- Extract CI domain logic into `src/devops_cli/ci/` as public functions.
- Route child processes through `run_subprocess` and isolate tests with `ProcessFake`.
- Move committed GitHub workflow assertions to `tests/invariants/test_workflows.py`.
- Dissolve monolithic `test_ci.py` and `test_devcontainer.py` into behaviour test files.
- Ensure all tests under `tests/commands/` for these modules have zero internal patches and zero private imports.

**Non-Goals:**
- Change CI check execution rules, gates, or output formats.
- Change command line options for `devops ci`, `test`, or `devcontainer`.

## Decisions

### 1. Remove `PYTEST_CURRENT_TEST` Detection
- **Decision**: Delete lines checking `os.getenv("PYTEST_CURRENT_TEST")` in `src/devops_cli/commands/ci.py` and remove `"PYTEST_CURRENT_TEST"` from `core/process.py`.
- **Alternative considered**: Keep `PYTEST_CURRENT_TEST` detection for safety during test runs.
  - *Rejected*: Rule 2 of AGENTS.md explicitly orders: "Stop also when you swallow an error, make product code detect tests, or put a second fix on a fix." Product code must never detect when it runs under test.

### 2. Extract CI Logic to `src/devops_cli/ci/`
- **Decision**: Move check definitions, gate cache access, result formatting, and coverage cleanup to `src/devops_cli/ci/gates.py` and `src/devops_cli/ci/coverage.py`. Make `commands/ci.py` a thin adapter.
- **Alternative considered**: Keep domain logic in `commands/ci.py`.
  - *Rejected*: Architectural standard requires `commands/` modules to serve as thin adapters over domain packages.

### 3. Move Workflow Invariant Tests to `tests/invariants/test_workflows.py`
- **Decision**: Extract tests validating committed GitHub workflow YAML files from `tests/commands/test_ci.py` into `tests/invariants/test_workflows.py`.
- **Alternative considered**: Keep workflow file assertions in `test_ci.py`.
  - *Rejected*: Tests asserting invariants on committed repository files belong in `tests/invariants/`, distinct from CLI command execution tests.

## Risks / Trade-offs

- [Coverage drop during test file split] → Run coverage verification after each test extraction to guarantee parity.
- [Worktree root resolution in tests] → Route root resolution to the active git worktree or temporary directory fixture.

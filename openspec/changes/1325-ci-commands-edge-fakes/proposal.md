# Proposal

## Why

Issue #1325 delivers Phase E package test refactoring for developer workflow commands (`devops ci`, `test`, `devcontainer`, `workspace`, `install-tools`, `uv`, `branches`, `pipeline`) under parent issue #1307. The tests covering these commands currently monkeypatch `devops_cli` internals (`_get_project_root`, `run_subprocess`, `_run`, `_download`), import private symbols, and rely on `PYTEST_CURRENT_TEST` detection branches in product code. This change migrates tests to edge fakes, removes `PYTEST_CURRENT_TEST` detection branches, moves CI domain logic into `src/devops_cli/ci/`, and moves workflow invariant assertions into `tests/invariants/test_workflows.py`.

## What Changes

- Remove `PYTEST_CURRENT_TEST` detection branches from `src/devops_cli/commands/ci.py` and `src/devops_cli/core/process.py`.
- Move check specs, gate cache, result assembly, and coverage cleanup functions into `src/devops_cli/ci/`.
- Ensure test-target selection is hosted under `src/devops_cli/core/test_selection.py` and called through public functions.
- Move workflow invariant tests from `tests/commands/test_ci.py` into `tests/invariants/test_workflows.py`.
- Remove internal patches and private imports across `tests/commands/` for `ci`, `test`, `devcontainer`, `workspace`, `install_tools`, `uv`, `branches`, and `pipeline`.
- Replace manual runners and doubles with `process_fake`, `keyring_store`, and `cli` fixtures.
- Delete `tests/commands/test_ci.py` and `tests/commands/test_devcontainer.py`, splitting their tests into behaviour files.
- This change alters no consumer-observed CLI behaviour or command syntax, so it sets `skip_specs: true`.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/commands/ci.py`: becomes a thin adapter delegating domain operations to `src/devops_cli/ci/`.
- `src/devops_cli/ci/`: receives public domain functions for gate execution, check specification, and coverage management.
- `src/devops_cli/core/process.py`: removes `PYTEST_CURRENT_TEST` environment pass-through.
- `tests/commands/`: tests exercise command interfaces via `process_fake` without patching internals.
- `tests/invariants/test_workflows.py`: hosts committed GitHub workflow and action invariants.

## Feasibility

- `tests/support/fakes/process.py` provides deterministic process execution for child commands.
- `tests/support/fakes/keyring.py` provides in-memory keyring storage for credentials.
- `src/devops_cli/ci/` already exists with cache and gate admission components.
- `src/devops_cli/core/test_selection.py` already exists and exports public selection logic.

## Existing Tool Considered

- `ProcessFake` isolates child process invocations.
- `KeyringFake` isolates secret storage.
- Using shared test fakes and domain modules eliminates 213 internal patch sites and 76 private imports, removing mock detection branches from product code.

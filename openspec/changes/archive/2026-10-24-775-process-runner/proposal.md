# Proposal

## Why

External tool execution has no single owner in the codebase (#775). Duplicate logic exists across sync and async runners, process group termination, and dry-run checks.

## What Changes

- Consolidate process execution into one runner in `src/devops_cli/core/process.py` for sync and async execution.
- Consolidate process group termination into `terminate_process_group` in `src/devops_cli/core/process.py`, replacing duplicate helpers in `sandbox/host.py` and `k8s/port_forward_daemon.py`.
- Handle dry-run decisions consistently in the process runner: mutating commands return `PlannedRequest` representations and do not execute, while declared local reads execute.
- Consolidate `uv --preview-features` argv preparation in `src/devops_cli/core/process.py`.
- Provide a seam for process execution and ship `ProcessFake` in `tests/support/fakes/process.py` with its contract suite in `tests/test_process_contract.py`.
- Replace `_LAZY_OBJECT_MAPPING` and `_get` blocks in command modules with standard function-local imports.
- This change alters no behavior that an external consumer observes. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/process.py`, `src/devops_cli/commands/branches.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/commands/uv.py`, `src/devops_cli/commands/workspace.py`, `src/devops_cli/sandbox/host.py`, `src/devops_cli/k8s/port_forward_daemon.py`.
- Tests: `tests/support/fakes/process.py`, `tests/test_process_contract.py`, `tests/test_process.py`, `tests/conftest.py`.
- Documents: `docs/TESTING.md`, `ARCHITECTURE.md`.

## Feasibility

- Verified `src/devops_cli/core/process.py` lines 351-748: `run_subprocess` and `run_subprocess_async` duplicate command validation, environment sanitization, token pinning, and tracing.
- Verified process group termination implementations in `src/devops_cli/sandbox/host.py:65` and `src/devops_cli/k8s/port_forward_daemon.py:78`. `ai/harness/shell.py` and `ai/review/review_environment.py:225` were already removed in earlier refactors.
- Verified `_LAZY_OBJECT_MAPPING` and `_get` blocks in `src/devops_cli/commands/branches.py`, `commands/ci.py`, `commands/uv.py`, and `commands/workspace.py`.
- Verified ADR 0007 (`docs/adr/0007-tests-double-only-process-edges.md`) and `docs/TESTING.md` which specify process edge doubles through one seam with a contract suite.

## Existing Tool Considered

Python stdlib `subprocess` and `asyncio.subprocess` provide core process primitives, but do not provide application-level token pinning, OpenTelemetry tracing, process-group timeout termination, or dry-run planning. The runner wraps standard library primitives with these requirements.

Internal code deleted or consolidated:
- `_terminate_process_group` duplicates in `sandbox/host.py` and `k8s/port_forward_daemon.py`
- `_LAZY_OBJECT_MAPPING` and `_get` helper blocks in `commands/branches.py`, `commands/ci.py`, `commands/uv.py`, and `commands/workspace.py`
- `_with_uv_preview` in `commands/ci.py` and manual preview flag injection in `commands/uv.py`

# Tasks

## 1. Process Group Lifecycle Consolidation

- [x] 1.1 Write failing tests for `terminate_process_group` in `tests/test_process.py` and verify failure with `uv run devops ci test tests/test_process.py`.
- [x] 1.2 Implement `terminate_process_group` in `src/devops_cli/core/process.py`, delegate from `sandbox/host.py` and `k8s/port_forward_daemon.py`, and verify with `uv run devops ci test tests/test_host_sandbox.py tests/test_k8s_port_forward_daemon.py tests/test_process.py`.

## 2. Process Runner Seam, Dry-Run Intent, and UV Flag Consolidation

- [x] 2.1 Write failing tests for `ProcessRunner` seam, `local_read` intent handling, dry-run `PlannedProcessResult`, and centralized uv flags in `tests/test_process.py` and verify with `uv run devops ci test tests/test_process.py`.
- [x] 2.2 Implement `ProcessRunner`, `DefaultProcessRunner`, seam functions (`get_process_runner`, `set_process_runner`, `reset_process_runner`), uv flag injection, and dry-run execution in `src/devops_cli/core/process.py`, remove duplicate uv flag injections in `commands/ci.py` and `commands/uv.py`, register reset in `tests/conftest.py`, and verify with `uv run devops ci test tests/test_process.py tests/test_ci.py tests/test_uv.py`.

## 3. ProcessFake and Contract Suite

- [x] 3.1 Write the process fake contract suite in `tests/test_process_contract.py` covering real `DefaultProcessRunner` and `ProcessFake` and verify initial failure with `uv run devops ci test tests/test_process_contract.py`.
- [x] 3.2 Implement `ProcessFake`, `ProcessAnswer`, and `process_fake` fixture in `tests/support/fakes/process.py` and verify contract suite passes with `uv run devops ci test tests/test_process_contract.py`.

## 4. Command Seams and Removal of Lazy Mapping Blocks

- [x] 4.1 Replace `_LAZY_OBJECT_MAPPING` and `_get` in `commands/branches.py`, `commands/ci.py`, `commands/uv.py`, and `commands/workspace.py` with standard function-local imports and verify with `uv run devops ci test tests/test_branches.py tests/test_ci.py tests/test_uv.py tests/test_workspace.py`.
- [x] 4.2 Regenerate documentation with `uv run devops docs generate --sync-readme` and verify full quality gate with `uv run devops ci`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Design

## Context

See proposal.md - Why.
External tool execution currently has duplicated logic across `run_subprocess` and `run_subprocess_async` in `src/devops_cli/core/process.py`.
Process-group termination is duplicated across `sandbox/host.py` and `k8s/port_forward_daemon.py`.
Multiple command modules use `_LAZY_OBJECT_MAPPING` and `_get` blocks for test patching.
ADR 0007 requires one seam per edge and one shared fake with a contract suite.

## Goals / Non-Goals

**Goals:**
- Provide a single process runner interface and implementation in `src/devops_cli/core/process.py`.
- Consolidate process group termination into `terminate_process_group` in `core/process.py`.
- Ensure `--dry-run` executes only declared local reads and returns a planned request representation for mutating commands.
- Centralize `uv --preview-features` argv preparation in `core/process.py`.
- Provide `ProcessFake` in `tests/support/fakes/process.py` and its contract suite in `tests/test_process_contract.py`.
- Replace `_LAZY_OBJECT_MAPPING` and `_get` blocks in command modules with standard function-local imports.

**Non-Goals:**
- Migrate all existing tests to `ProcessFake` in this single pull request.
- Remove GitPython (tracked separately).

## Decisions

### Decision 1: ProcessRunner Seam and Interface
Define `ProcessRunner` Protocol in `src/devops_cli/core/process.py` with `run` and `run_async` methods.
`DefaultProcessRunner` implements real execution.
Module-level functions `get_process_runner()`, `set_process_runner()`, and `reset_process_runner()` provide the test seam.
`run_subprocess` and `run_subprocess_async` delegate to `get_process_runner()`.

*Alternatives considered:*
- Passing the runner down the call tree as a parameter: rejected by ADR 0007 because it adds clutter to hundreds of signatures without architectural benefit.

### Decision 2: Dry-run and Planned Request Handling
In `run` and `run_async`, inspect `is_dry_run()`.
If active and the command is not a declared local read (`local_read=True` or `intent in {"read", "local_read"}`):
Print the dry-run command if not quiet.
Return a `PlannedProcessResult` object that provides both `PlannedRequest` and `subprocess.CompletedProcess[str]` interfaces.

*Alternatives considered:*
- Returning bare `PlannedRequest`: rejected because existing callers expect `proc.returncode` and `proc.stdout`.
- Printing only and running anyway: rejected by the constraint that `--dry-run` never executes a mutating command.

### Decision 3: Process-group Lifecycle Consolidation
Consolidate process group termination into `terminate_process_group(pid: int, sig: int = signal.SIGTERM) -> bool` in `core/process.py`.
Guard against non-integers, PID <= 1, self PID, and self PGID.
When PGID equals own PGID, fall back to `os.kill(pid, sig)`.
`sandbox/host.py` and `k8s/port_forward_daemon.py` delegate their helpers to `core.process.terminate_process_group`.

*Alternatives considered:*
- Leaving separate implementations in each module: rejected because duplicate code drifts and misses security guards.

### Decision 4: Centralized UV Flags
In `core/process.py`, inspect `cmd[0]`.
When `cmd[0] == "uv"` and `"--preview-features"` is not in `cmd`, inject `["--preview-features", "malware-check,check-command"]`.
Remove redundant manual injections from `commands/ci.py` and `commands/uv.py`.

*Alternatives considered:*
- Keeping separate flags in commands: rejected because consistent tool execution belongs in the runner.

### Decision 5: ProcessFake and Contract Suite
Implement `ProcessFake` in `tests/support/fakes/process.py`.
The fake records calls, allows scripting responses via `ProcessAnswer`, simulates `shutil.which` for tools other than git and bwrap, and enforces dry-run rules.
`tests/test_process_contract.py` validates that `DefaultProcessRunner` and `ProcessFake` fulfill the contract.

*Alternatives considered:*
- Global monkeypatching of `subprocess.run`: rejected by ADR 0007.

## Risks / Trade-offs

- [Risk] Callers expecting exact `subprocess.CompletedProcess` type match under dry run.
  Mitigation: `PlannedProcessResult` inherits from `PlannedRequest` and is registered as a virtual subclass of `subprocess.CompletedProcess`.
- [Risk] Command help import performance if heavy modules are imported statically.
  Mitigation: Use function-local imports in command functions instead of module-level imports.

# Task 780: Async Process Runner Redacts Telemetry and Kills Process Group on Timeout

**Issue**: [#780](https://github.com/dan-petty/devops-cli/issues/780)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/security, scope/cli

---

## 1. Description & Objectives

The async subprocess runner (`run_subprocess_async` in `src/devops_cli/core/process.py`) had drifted from the synchronous `run_subprocess` implementation in two critical ways:
1. **Telemetry Command Leakage**: `run_subprocess_async` was joining the first 8 raw argv elements directly into `cmd_summary` without sanitization, allowing secret tokens, credentials, and sensitive arguments to reach OpenTelemetry trace attributes (`subprocess.cmd` and `process.command_line`), whereas the sync path invoked `_sanitize_command_for_telemetry`.
2. **Process Group Leakage on Timeout**: On timeout, `run_subprocess_async` called `proc.kill()` solely on the direct child process without isolating the child into a dedicated session, leaving grandchild processes (such as spawned test workers, background subshells, or compilers) running indefinitely as orphaned processes.

This deliverable:
- Aligns `run_subprocess_async` with `_sanitize_command_for_telemetry(cmd)` so all telemetry command attributes mask secrets, credentials, and parameters identically to the sync path.
- Spawns async subprocesses with POSIX process group isolation (`start_new_session=True`).
- Implements resilient process group termination on timeout (`_terminate_process_group_async`, `_signal_process_group`, `_wait_for_group_exit_async`), cleanly escalating from `SIGTERM` to `SIGKILL` while strictly guarding against signalling PID 1, PID 0, or the caller's own process group.
- Adds comprehensive tests covering secret-bearing argv sanitization, grandchild process group cleanup upon timeout, and process group guard invariants.

---

## 2. Acceptance Criteria

- [x] The async path sanitizes the telemetry command the same way as the sync path.
- [x] A timeout kills the whole process group rather than only the direct child.
- [x] Tests cover a secret-bearing argv and a child that starts its own child.
- [x] Changelog fragment `changelog.d/780.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `src/devops_cli/core/process.py`: Telemetry command sanitization and process group termination on timeout.
- [x] `tests/test_process.py`: Unit tests for telemetry secret masking, grandchild timeout termination, and pgid guard helpers.
- [x] `changelog.d/780.md`: Changelog entry.
- [x] `docs/agent/tasks/task-780-async-process-runner-telemetry-redaction-and-pgid-kill.md`: Task documentation.

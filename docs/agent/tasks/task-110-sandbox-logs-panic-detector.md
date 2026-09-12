# Task 110: Streaming Diagnostic Log Aggregator and Panic Detector (`devops sandbox logs`)

**Issue**: [#110](https://github.com/dan-petty/devops-cli/issues/110)
**PR**: [#179](https://github.com/dan-petty/devops-cli/pull/179) (Draft)
**Status**: In Progress
**Milestone**: `v0.2.17`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`

---

## 1. Description & Architectural Objectives

Implement multiplexed stdout/stderr log streaming with follow mode (`-f` / `--follow`), real-time regex panic/crash detection (Python tracebacks, Go panics, Java stacktraces, Rust panics, segfaults/fatal OS signals), structured incident record persistence under `.data/sandbox/incidents/<id>.json`, and terminal log rendering via `devops sandbox logs`.

### Key Architectural Capabilities

1. **Multiplexed Log Streaming & Buffer Management**:
   - Stream container stdout and stderr in follow mode or batch tail mode.
   - Demultiplex and label output streams (stdout vs stderr).
   - Support `--tail`, `--timestamps`, `--follow`, `--no-panic-detect`, `--incident-dir`, `--json`, and `--dry-run`.

2. **Automated Multi-Language Panic Detection Engine (`src/devops_cli/sandbox/logs.py`)**:
   - Streaming state machine detecting multi-line stacktraces and single-line fatal crashes:
     - Python: `Traceback (most recent call last):` -> `File ...` -> exception type.
     - Go: `panic: ...` / `fatal error: ...` -> `goroutine \d+ \[...\]:` -> stack frames.
     - Java: `Exception in thread ...` / `...Exception: ...` -> `\tat ...`.
     - Rust: `thread '...' panicked at ...` -> `stack backtrace:`.
     - Segfaults / Signals: `Segmentation fault`, `SIGSEGV`, `SIGABRT`, `SIGBUS`, `SIGILL`, `Aborted`.
   - Summary messages bounded to $\le 256$ chars to adhere to repository error bounded length invariants (CWE-209 / CWE-400).

3. **Structured Incident Record Persistence**:
   - Archive detected panics into `.data/sandbox/incidents/<incident_id>.json`.
   - Protect file paths against traversal with `validate_no_path_traversal`.

4. **Terminal Log Visualizer & CLI Command (`devops sandbox logs`)**:
   - Stream logs with Rich coloring (timestamps, stderr highlighting).
   - Display prominent Rich alert panels upon panic detection with incident metadata and JSON archive link.
   - Structured JSON output mode for programmatic consumption.

5. **Architectural Invariants & Quality Standards**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.
   - Strict hostname standard: Strictly use `example.com` (no subdomains) for mock/dummy test values.
   - Maintain $\ge 90\%$ test coverage across `src/devops_cli/sandbox/`.

---

## 2. Planned Changes

1. **Sandbox Models Layer (`src/devops_cli/sandbox/models.py`)**:
   - Add `PanicType` enum.
   - Add `PanicIncident`, `SandboxLogLine`, and `SandboxLogsReport` Pydantic v2 models.

2. **Logs & Panic Detection Subsystem (`src/devops_cli/sandbox/logs.py`)**:
   - Implement `PanicDetector` streaming line accumulator.
   - Implement `archive_incident` persistence function.
   - Implement batch line parser.

3. **Engine Integration (`src/devops_cli/sandbox/engine.py`)**:
   - Add `logs()` method to `WorkloadSandboxEngine` using Docker SDK and subprocess fallback.

4. **CLI Command & Help (`src/devops_cli/commands/sandbox.py` & `src/devops_cli/lang/en/help.py`)**:
   - Implement `devops sandbox logs` command with `--follow`, `--tail`, `--timestamps`, `--json`, and `--dry-run`.
   - Add help catalog definitions.

5. **Submodule-Aligned Tests (`tests/test_sandbox_logs.py`)**:
   - Unit tests for panic detector regexes and multi-line frame tracking.
   - Unit tests for incident archiving and traversal protection.
   - Unit and integration tests for engine `logs()` and CLI `devops sandbox logs`.

---

## 3. Implementation Checklist

- [x] Ground issue [#110](https://github.com/dan-petty/devops-cli/issues/110) and update status label to `status/in-progress`.
- [x] Synchronize GitHub Projects card to `In Progress`.
- [x] Create topic branch `feat/110-sandbox-logs-panic-detector`.
- [x] Author task document `docs/agent/tasks/task-110-sandbox-logs-panic-detector.md`.
- [x] Implement data models in `src/devops_cli/sandbox/models.py`.
- [x] Implement panic detection and incident archiving in `src/devops_cli/sandbox/logs.py`.
- [x] Implement `WorkloadSandboxEngine.logs()` in `src/devops_cli/sandbox/engine.py`.
- [x] Implement CLI command `devops sandbox logs` in `src/devops_cli/commands/sandbox.py`.
- [x] Add help strings in `src/devops_cli/lang/en/help.py`.
- [x] Author comprehensive tests in `tests/test_sandbox_logs.py`.
- [x] Run test suite and verify test coverage $\ge 90\%$ (94.3% achieved).
- [x] Validate cyclomatic complexity $\le 10$ and architectural invariants.
- [x] Run full `devops ci` quality gate.
- [x] Open draft PR [#179](https://github.com/dan-petty/devops-cli/pull/179) on GitHub and monitor CI checks.

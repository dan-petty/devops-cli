# Task 199: Deterministic Async Memory & Connection Pool Profiler

**Issue**: [#199](https://github.com/dan-petty/devops-cli/issues/199)
**Status**: Done
**Milestone**: `v0.2.17`
**Priority**: `priority/p2-medium`
**Scope**: `scope/test`

---

## 1. Description & Architectural Objectives

Implement a deterministic async memory and connection pool profiler under `devops test profile-memory` as specified in the `v0.2.17` roadmap:
1. **Diagnostic Memory Profiling (`devops test profile-memory`)**:
   - Leverage Python `tracemalloc` to snapshot, measure, and analyze heap allocations.
   - Profile memory across configurable targets: `fastmcp` server tools, `http-pool` async client connections, custom CLI commands, or arbitrary Python modules/callables.
   - Track peak memory usage, net allocated delta, top allocation source lines, and object counts.
2. **Socket Lifecycle & Connection Pool Leak Detection**:
   - Inspect active socket descriptors and connection broker states to assert proper socket closing and connection recycling.
   - Detect leaked socket instances, unclosed streams, and unbounded connection pool growth.
3. **Threshold Guardrails & Reporting**:
   - Enforce configurable peak memory thresholds (`--max-peak-mb`) and socket leak thresholds (`--fail-on-leak`).
   - Rich tabular display and structured JSON export (`--json`, `--output`).
4. **Architectural Invariants & Quality Standards**:
   - Strict cyclomatic complexity $\le 10$ and maximum nesting depth $\le 5$ project-wide.
   - Comprehensive unit and integration test coverage $\ge 90\%$.
   - Bounded string truncation ($\le 256$ chars) on all error details.

---

## 2. Planned Changes

1. **`src/devops_cli/test/memory_profiler.py`**:
   - Data models: `MemoryProfileItem`, `MemoryProfileReport`.
   - Engine: `MemoryProfiler` class managing `tracemalloc` lifecycle, snapshot diffing, top allocation extraction, and socket counting.
   - Target handlers: `profile_async_callable`, `profile_http_broker_pool`, `profile_fastmcp_tools`, `profile_cli_command`.
2. **`src/devops_cli/test/__init__.py`**:
   - Export memory profiler symbols.
3. **`src/devops_cli/commands/test_cmd.py`**:
   - Register `profile-memory` subcommand with CLI options:
     - `target`: Target workload to profile (`fastmcp`, `http-pool`, `command`, `callable`).
     - `--duration` / `-d`: Sample duration in seconds.
     - `--iterations` / `-i`: Iterations count.
     - `--top` / `-t`: Number of top allocations to report.
     - `--max-peak-mb`: Peak memory threshold in megabytes.
     - `--fail-on-leak`: Exit with non-zero code on detected socket leak.
     - `--json`: Format output as JSON.
     - `--output` / `-o`: Export report to file.
     - `--dry-run`: Dry-run mode support.
4. **`src/devops_cli/lang/en/help.py` & `messages.py`**:
   - Add help text and localized strings for `profile-memory`.
5. **`tests/test_memory_profiler.py`**:
   - Comprehensive unit tests covering snapshots, diffing, socket leak detection, CLI invocations, and error handling with $\ge 90\%$ coverage.

---

## 3. Progress Tracking

- [x] Ground issue in GitHub tracking (#199) with `status/in-progress`.
- [x] Author task tracking file `docs/agent/tasks/task-199-async-memory-profiler.md`.
- [x] Checkout dedicated topic branch `feat/199-async-memory-profiler`.
- [x] Implement `src/devops_cli/telemetry/memory_profiler.py`.
- [x] Register CLI subcommand `devops test profile-memory` in `src/devops_cli/commands/test_cmd.py` and update `help.py`.
- [x] Author unit tests in `tests/test_memory_profiler.py` (24/24 passing).
- [x] Run quality gates (`devops scan complexity`, `ruff`, `mypy`, `pytest`, `devops docs generate --sync-readme`).
- [x] Open Pull Request [#200](https://github.com/dan-petty/devops-cli/pull/200) targeting `release/v0.2.17`.
- [x] Remediate Copilot review comments and post in-thread replies on PR #200.
- [x] Implement `devops pr threads resolve-all` and `--auto-resolve` for merge readiness check in CI.
- [ ] Monitor CI checks until green, then squash-merge into `release/v0.2.17`.

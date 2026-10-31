# Design

## Problem Statement

Multiple test modules wait for asynchronous operations (threads, child processes, or thread barriers) using short hardcoded timeout values (such as 1 s, 5 s, 10 s, or 30 s). Under heavy CPU contention, scheduled threads may stall longer than these brief intervals, causing test suites to fail intermittently even when behavior is correct.

`docs/TESTING.md` establishes standard patterns:
1. Waits expecting an event or completion from another thread must wait with `THREAD_HANDOFF_BOUND_SECONDS` (30 s).
2. Waits observing a spawned subprocess must wait via `wait_while_running(condition, process)` and exit waits must have no internal timeout, letting hangs be caught by the pytest runner hang bound.
3. Tests verifying that an event does not happen must keep a documented quiet window.

## Proposed Changes

### Thread and Future Waits

In:
- `tests/telemetry/test_trace_propagation.py`
- `tests/http/test_http_connection_pool.py`
- `tests/ai/client/test_ai_client_network.py`
- `tests/github/test_github_session.py`
- `tests/ui/test_ui_dashboard_state_store.py`
- `tests/ui/test_ui_log_pane.py`
- `tests/ui/test_ui_refresh_coordination.py`
- `tests/ui/test_ui_shutdown.py`
- `tests/ui/test_ui_virtualized_log_buffer.py`

Replace all explicit `timeout=5`, `timeout=10`, and similar values with `THREAD_HANDOFF_BOUND_SECONDS` imported from `tests.support.waits`.

### Subprocess Waits

In `tests/github/test_github_session.py::test_a_process_that_sent_a_request_exits_without_closing_its_session`:
Replace `subprocess.run(..., timeout=30)` with `subprocess.Popen` plus `wait_while_running`, followed by `proc.wait()`.

In `tests/commands/test_cli_startup_imports.py::test_startup_structural_budget_passes_under_cpu_load`:
Replace `p.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)` in process cleanup with `wait_while_running(lambda: p.poll() is not None, p)`.

### Quiet Window Constants

In `tests/k8s/test_k8s_port_forward_daemon.py` and `tests/roadmap/test_roadmap_github_store.py`:
Declare named module constants for the quiet check intervals (`_QUIET_SECONDS`), matching the pattern in `tests/github/test_service_limits.py`.

## Acceptance Criteria Verification

1. `git grep -n 'wait(.*timeout=[0-9]\|join(timeout=[0-9])' ...` returns 0 lines across all target test files.
2. `git grep -n 'wait_while_running' tests/commands/test_cli_startup_imports.py tests/github/test_github_session.py` confirms presence of `wait_while_running` in both files.
3. Each affected test file passes repeatedly (`uv run devops ci test <file>`).

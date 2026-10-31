# Proposal

## Why

Issue #2138 records that test files keep hardcoded deadlines (5 s, 10 s, 30 s) when waiting for threads, events, or processes. On loaded hosts, these fixed timeouts can elapse before scheduled threads run, causing flaky test failures even though the production code functions correctly.

Following the principles established in issue #2092 and documented in `docs/TESTING.md`:
- Tests waiting for events from another thread or process must use `THREAD_HANDOFF_BOUND_SECONDS` from `tests.support.waits`, or an event-driven mechanism.
- Tests waiting for an event from a started subprocess must use `wait_while_running(condition, process)` and wait for process exit without an internal deadline, letting hangs fail at the pytest hang bound.
- Negative checks that verify an event does not occur must keep a documented quiet window.

## What Changes

- Update tests in `tests/telemetry/test_trace_propagation.py`, `tests/http/test_http_connection_pool.py`, `tests/ai/client/test_ai_client_network.py`, `tests/github/test_github_session.py`, `tests/commands/test_cli_startup_imports.py`, and the migrated UI tests (`tests/ui/test_ui_dashboard_state_store.py`, `tests/ui/test_ui_log_pane.py`, `tests/ui/test_ui_refresh_coordination.py`, `tests/ui/test_ui_shutdown.py`, `tests/ui/test_ui_virtualized_log_buffer.py`) to use `THREAD_HANDOFF_BOUND_SECONDS` instead of hardcoded 5 s or 10 s timeouts.
- Update `test_a_process_that_sent_a_request_exits_without_closing_its_session` in `tests/github/test_github_session.py` and worker joins in `tests/commands/test_cli_startup_imports.py` to use `wait_while_running`.
- Ensure quiet check windows in `tests/k8s/test_k8s_port_forward_daemon.py` and `tests/roadmap/test_roadmap_github_store.py` use named quiet constants rather than literal timeout arguments.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/telemetry/test_trace_propagation.py`: Replace 5 s timeouts on thread joins and future results with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/http/test_http_connection_pool.py`: Replace 10 s timeouts on barrier and thread joins with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/ai/client/test_ai_client_network.py`: Replace 1 s, 5 s, and 10 s timeouts on barrier, events, and joins with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/github/test_github_session.py`: Replace 30 s subprocess run timeout with `wait_while_running` and replace 10 s join with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/commands/test_cli_startup_imports.py`: Replace process wait timeout with `wait_while_running`.
- `tests/ui/test_ui_dashboard_state_store.py`: Replace 5 s timeouts with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/ui/test_ui_log_pane.py`: Replace 10 s gate timeout with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/ui/test_ui_refresh_coordination.py`: Replace 5 s timeouts with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/ui/test_ui_shutdown.py`: Replace hardcoded 30 s release wait with unbound wait released in finally.
- `tests/ui/test_ui_virtualized_log_buffer.py`: Replace 5 s and 10 s thread joins with `THREAD_HANDOFF_BOUND_SECONDS`.
- `tests/k8s/test_k8s_port_forward_daemon.py`: Use named quiet window constants for negative event checks.
- `tests/roadmap/test_roadmap_github_store.py`: Use named quiet window constant for negative write check.

## Feasibility

- All changes update test code to follow the conventions in `docs/TESTING.md`.
- `THREAD_HANDOFF_BOUND_SECONDS` and `wait_while_running` already exist in `tests/support/waits.py`.
- No product logic is altered.

## Existing Tool Considered

`tests/support/waits.py` provides the canonical wait helpers (`THREAD_HANDOFF_BOUND_SECONDS`, `wait_until`, and `wait_while_running`). No external libraries are needed.

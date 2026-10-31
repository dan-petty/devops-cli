# Tasks

- [x] Update `tests/telemetry/test_trace_propagation.py` thread joins and future timeouts to `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 1 -->
- [x] Update `tests/http/test_http_connection_pool.py` barrier and thread join timeouts to `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 2 -->
- [x] Update `tests/ai/client/test_ai_client_network.py` barrier, event, and thread join timeouts to `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 3 -->
- [x] Update `tests/github/test_github_session.py` to use `wait_while_running` and `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 4 -->
- [x] Update `tests/commands/test_cli_startup_imports.py` to use `wait_while_running`. <!-- id: 5 -->
- [x] Update migrated UI test files (`test_ui_dashboard_state_store.py`, `test_ui_log_pane.py`, `test_ui_refresh_coordination.py`, `test_ui_shutdown.py`, `test_ui_virtualized_log_buffer.py`) to use `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 6 -->
- [x] Update quiet window waits in `tests/k8s/test_k8s_port_forward_daemon.py` and `tests/roadmap/test_roadmap_github_store.py` to use named constants. <!-- id: 7 -->
- [x] Verify all acceptance criteria and run tests under `uv run devops ci test`. <!-- id: 8 -->

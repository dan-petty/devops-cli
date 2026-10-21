# Task: Hermetic Floor Edge Denial and Process-Wide State Reset (#1310)

**Issue**: [#1310](https://github.com/dan-petty/devops-cli/issues/1310)
**Feasibility**: Verified against `tests/conftest.py`, `tests/cluster_secret_fakes.py`, `tests/test_architectural_invariants.py`, `docs/TESTING.md`, and the 59 modules in `src/devops_cli/` carrying module-level mutable bindings, `@lru_cache`/`@cache` functions, `ContextVar` bindings, and class-level mutable attributes.

## Summary

Completed the hermetic test floor in `tests/conftest.py` so every unfaked process, network (TCP, DNS, and `AF_UNIX`), or keyring reach fails with a uniform `<edge> edge reached without a fake: <target>` error and records the reach for teardown enforcement, and every piece of process-wide state in `src/devops_cli/` is reset between tests.

## Deliverables

- [x] Added public reset functions across stateful modules in `src/devops_cli/` and wired `reset_process_wide_state` in `tests/conftest.py` to reset every module-level mutable binding, `@lru_cache`/`@cache` function, `ContextVar`, and class-level mutable attribute before and after each test.
- [x] Added `test_every_piece_of_process_wide_state_in_src_is_reset_by_the_floor` and `test_process_wide_state_invariant_reports_each_unreset_form` in `tests/test_architectural_invariants.py` to verify AST coverage of all process-wide state in `src/devops_cli/` and all four unreset forms.
- [x] Updated `prevent_external_network_calls`, `refuse_real_programs`, `deny_real_keyring`, and `unexpected_loopback_connects` in `tests/conftest.py` to enforce uniform `<edge> edge reached without a fake: <target>` failures across process, network (loopback, non-loopback, DNS, and `AF_UNIX`), and keyring edges, with `@pytest.mark.live(...)` and `@pytest.mark.unreachable(...)` marker support.
- [x] Added `config` and `cli` shared fixtures in `tests/conftest.py`, defaulted `telemetry.enabled` to `false` in the floor configuration, and deleted `forbid_requests` from `tests/cluster_secret_fakes.py`.
- [x] Added `tests/invariants/test_hermetic_floor.py` exercising each edge guard and marker in a child pytest session via `pytester`, and updated `docs/TESTING.md`.

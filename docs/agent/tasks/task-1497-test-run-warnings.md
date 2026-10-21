# Task #1497 — Fix Unclosed SQLite Test Connections, Package Introspector Deprecation Warnings, and Starlette Lock Entry

**Issue**: [#1497](https://github.com/dan-petty/devops-cli/issues/1497)
**Feasibility**: Confirmed against Python 3.14 `sqlite3.connect` context manager semantics, `src/devops_cli/ai/library/introspector.py` (`PackageIntrospector.introspect_package`), and `uv.lock` (`starlette` `1.6.0` vs `1.9.0`). Entering `with sqlite3.connect(path) as conn:` commits or rolls back the transaction on exit without closing `conn`, emitting `ResourceWarning: unclosed database` under garbage collection in 15 test sites across five test modules; `inspect.getmembers` in `PackageIntrospector.introspect_package("pydantic", max_depth=1)` accesses `pydantic.config.Extra` attributes and triggers `PydanticDeprecatedSince20`; and `starlette==1.6.0` imported the deprecated `anyio.abc.BlockingPortal` alias in `starlette.testclient`.

## Summary

Closed the 15 direct `sqlite3.connect(...)` test connections with `contextlib.closing`, scoped `DeprecationWarning` suppression around module symbol extraction in `PackageIntrospector.introspect_package`, and upgraded `starlette` in `uv.lock` to `1.9.0`.

## Deliverables

- [x] Wrap all 15 direct `with sqlite3.connect(...) as conn:` blocks in `tests/test_ai_served_by.py`, `tests/test_ai_spend_dispatch.py`, `tests/test_ai_spend_ledger.py`, `tests/test_review_profile.py`, and `tests/test_telemetry_instruments.py` with `contextlib.closing(sqlite3.connect(...))` (combining `, conn` where the block writes).
- [x] Suppress `DeprecationWarning` with `warnings.catch_warnings()` around module symbol extraction in `PackageIntrospector.introspect_package` (`src/devops_cli/ai/library/introspector.py`) so inspecting a library's API catalogue does not leak attribute-access deprecation warnings from the target package.
- [x] Add `@pytest.mark.filterwarnings("error::DeprecationWarning")` to `test_introspect_installed_package`, `test_cli_ai_ingest_library`, and `test_cli_ai_ingest_library_json_format` in `tests/test_library_ingest.py`.
- [x] Upgrade `starlette` from `1.6.0` to `1.9.0` in `uv.lock` to remove the `anyio.abc.BlockingPortal` deprecation warning from `starlette.testclient`.
- [x] Add changelog fragment `changelog.d/1497.md`.

## Verification

- [x] Verified `pytest -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning tests/test_ai_spend_ledger.py tests/test_ai_spend_dispatch.py tests/test_review_profile.py tests/test_telemetry_instruments.py` passes with zero warnings.
- [x] Verified `pytest -W error::DeprecationWarning tests/test_library_ingest.py tests/test_server.py tests/test_server_service.py tests/test_server_stream.py` passes with zero warnings.
- [x] Verified `uv run devops ci fail-to-pass --base origin/release/v0.2.38` and `uv run devops ci` pass.

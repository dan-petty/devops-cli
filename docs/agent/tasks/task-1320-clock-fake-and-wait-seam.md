# Task #1320: Clock Fake Backed by `time-machine` and Waiting Seam

**Issue**: [#1320](https://github.com/dan-petty/devops-cli/issues/1320)
**Feasibility**: Verified against `tenacity.RetryCallState` / `pydantic_ai.retries.RetryConfig` (`sleep` parameter bound at transport creation in `src/devops_cli/ai/retries/__init__.py`) and `ratelimit.limits(calls=60, period=60, clock=...)` (clock callable bound when the decorator is constructed in `src/devops_cli/github/rate_limiter.py`), confirming both accept call-time functions supplied by `devops_cli.core.clock`.

## Summary

- Added `time-machine==3.5.1` to the `dev` dependency group in `pyproject.toml` and `uv.lock`.
- Created `src/devops_cli/core/clock.py` exposing `sleep`, `async_sleep`, and `monotonic` so call-time waiting and monotonic clock reads go through a single seam without import-time function capture.
- Updated `create_retry_transport` and `create_async_retry_transport` in `src/devops_cli/ai/retries/__init__.py` to pass `sleep=clock.sleep` and `sleep=clock.async_sleep` to `RetryConfig`.
- Updated `GitHubRateLimiter.__init__` in `src/devops_cli/github/rate_limiter.py` to construct its burst-limit decorator per instance with `limits(calls=60, period=60, clock=clock.monotonic)` instead of capturing `time.monotonic` at module import time.
- Added `ClockFake` and the `clock` pytest fixture in `tests/support/fakes/clock.py` (registered via `tests/support/bootstrap.py`), paired with the fake-and-real contract test suite in `tests/core/test_clock_contract.py`.
- Migrated `tests/test_pydantic_ai_retries.py` and `tests/test_github_rate_limiter.py` to use `clock: ClockFake` and removed all `time.sleep` / `time.time` patches and real `time.sleep` calls.
- Replaced wall-clock elapsed assertions in `tests/test_ai_request_priority.py` (`test_as_available_non_blocking_when_full`) and `tests/test_server_service.py` (`test_a_drain_during_a_pause_stops_the_workers_without_running_the_held_rounds`), with `ServiceManager.drain_and_stop` returning whether all workers drained and stopped within the timeout.

## Deliverables

- [x] `src/devops_cli/core/clock.py` (`sleep`, `async_sleep`, `monotonic`)
- [x] `src/devops_cli/ai/retries/__init__.py` and `src/devops_cli/github/rate_limiter.py` routed through `devops_cli.core.clock`
- [x] `tests/support/fakes/clock.py` (`ClockFake`, `clock` fixture) and `tests/core/test_clock_contract.py`
- [x] `tests/test_pydantic_ai_retries.py`, `tests/test_github_rate_limiter.py`, `tests/test_ai_request_priority.py`, `src/devops_cli/server/service.py`, and `tests/test_server_service.py` migrated
- [x] `changelog.d/1320.md`

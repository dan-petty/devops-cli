# Proposal: #5891

## Why
`ProcessFake.run`, `ProcessFake.run_async`, and `ProcessFake.spawn_detached` record the caller environment and return scripted answers without calling `build_subprocess_env`. As a result, a caller that passes a refused override such as `PYTEST_ADDOPTS` passes every unit test over `process_fake` and fails with `SecurityError` in production (#5887).

## What Changes
- Update `ProcessFake.run`, `ProcessFake.run_async`, and `ProcessFake.spawn_detached` in `tests/support/fakes/process.py` to validate environment overrides and flags via `build_subprocess_env(env=env, isolate_env=isolate_env, extra_allowed_keys=extra_allowed_env)` before returning a result or detached child.
- Add an optional `env: dict[str, str] | None = None` parameter to `ProcessFake.spawn_detached`, record it on `ProcessCall`, and record `isolate_env` and `extra_allowed_env` on the `ProcessCall` produced by `ProcessFake.run_async` as `ProcessFake.run` already does.
- Add tests in `tests/core/test_process_fake_env.py` covering sync, async, and detached refusal of denied keys, flag forwarding to `build_subprocess_env` and `ProcessCall`, and passthrough of allowed overrides.
- Update any existing test or caller uncovered by running the full test suite under the real check.

## Capabilities
- `subprocess-environment`: extend the subprocess environment contract so the process fake enforces `build_subprocess_env` across `run`, `run_async`, and `spawn_detached`.

## Impact
- Tests using `process_fake` immediately catch prohibited environment overrides (`PYTEST_ADDOPTS`, loader variables, disallowed git keys) instead of masking production failures.
- No production runtime dependency changes; production `DefaultProcessRunner` already enforces `build_subprocess_env`.

## Feasibility
Confirmed against `origin/main`:
- `tests/support/fakes/process.py:269-437` (`ProcessFake.run`, `spawn_detached`, `run_async`) never calls `build_subprocess_env`; `spawn_detached` accepts no `env` parameter, and `run_async` does not record `isolate_env` or `extra_allowed_env` on `ProcessCall`.
- `src/devops_cli/core/process.py:193-244` defines `build_subprocess_env(env=..., isolate_env=..., extra_allowed_keys=...)` which raises `SecurityError("Prohibited dangerous environment variable override: '<key>'")` on refused overrides.
- `tests/roadmap/implement/test_roadmap_implement_strength.py:109-129` notes that `ProcessFake` checks nothing and had to manually invoke `build_subprocess_env`.

## Existing Tool Considered
The alternatives check on issue #5891 recorded `not-applicable` (`class: test`, no external tool search). The change reuses the project's existing `ProcessFake` test double (`tests/support/fakes/process.py`) and real sanitizer `build_subprocess_env` (`src/devops_cli/core/process.py`) rather than introducing any external library or duplicating validation rules. Estimated build cost: 30k-60k tokens and 2-4 hours, with negligible ongoing maintenance since rules stay solely in `build_subprocess_env`.

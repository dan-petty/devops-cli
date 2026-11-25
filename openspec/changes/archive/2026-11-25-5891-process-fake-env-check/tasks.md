# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests in `tests/core/test_process_fake_env.py` verifying that `ProcessFake.run`, `ProcessFake.run_async`, and `ProcessFake.spawn_detached` invoke `build_subprocess_env` with `env`, `isolate_env`, and `extra_allowed_env`, raise `SecurityError` on refused keys, record the flags on `ProcessCall`, and return scripted answers for allowed overrides
  - Verification: `$ uv run devops ci test tests/core/test_process_fake_env.py`
- [x] 1.2 Implement `build_subprocess_env` validation, optional `env` on `spawn_detached`, and flag recording on `run_async` in `tests/support/fakes/process.py`, and reconcile any tests exposed by running the full test suite
  - Verification: `$ uv run devops ci test tests/core/test_process_fake_env.py tests/core/test_subprocess_env_boundary.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec changes, docs checks, and static checks against `origin/main`
  - Verification: `$ uv run devops openspec check`

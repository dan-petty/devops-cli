# Tasks

## 1. Refuse the three code-loading keys

Reads: `src/devops_cli/core/process.py`, `src/devops_cli/config/constants.py`, `ARCHITECTURE.md`. Changes: `src/devops_cli/config/constants.py`, `tests/core/test_process_env_guard.py` (new).

- [ ] 1.1 Write a failing test in `tests/core/test_process_env_guard.py` that calls `build_subprocess_env(env={"GOFLAGS": "x"})`, `build_subprocess_env(env={"YARN_YARN_PATH": "x"})` and `build_subprocess_env(env={"UV_ENV_FILE": "x"})` and expects `SecurityError` for each, and verify that `uv run devops ci test tests/core/test_process_env_guard.py` fails on the base
- [ ] 1.2 Add `GOFLAGS`, `YARN_YARN_PATH` and `UV_ENV_FILE` to `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py`. Keep `UV_TOOL_DIR` and `npm_config_cache` out of the list. Run the test, and verify that `uv run devops ci test tests/core/test_process_env_guard.py` passes

## 2. Document the refused and accepted keys

Reads: `ARCHITECTURE.md`, `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`. Changes: `ARCHITECTURE.md`.

- [ ] 2.1 In the Uv and npm child environment bullet of `ARCHITECTURE.md`, name `GOFLAGS`, `YARN_YARN_PATH` and `UV_ENV_FILE` as refused. Name `UV_TOOL_DIR` and `npm_config_cache` as accepted, with the reason that they name directories and start no caller-named program. State that no live probe ran for `go` and `yarn` in the devcontainer, and verify that `uv run devops ci docs` passes
- [ ] 2.2 ARCHITECTURE.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

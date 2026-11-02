# Proposal

## Why

The subprocess guard accepts GOFLAGS, YARN_YARN_PATH and UV_ENV_FILE from a caller. These keys can make a child run caller-named code. #2750 requires a probe result and a refusal for each dangerous key.

## What Changes

- Add `GOFLAGS`, `YARN_YARN_PATH` and `UV_ENV_FILE` to `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py`.
- Add offline tests in `tests/core/test_process_env_guard.py` that `build_subprocess_env` raises `SecurityError` for each key.
- Document `UV_TOOL_DIR` and `npm_config_cache` as accepted directory keys in `ARCHITECTURE.md`.
- Record that no live probe ran for `go` and `yarn` in the devcontainer.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: Refuse Go, Yarn and uv file keys

## Impact

- Code: `src/devops_cli/config/constants.py`
- Documents: `ARCHITECTURE.md`
- Tests: `tests/core/test_process_env_guard.py`

## Feasibility

- The premise is confirmed: `_is_env_override_refused` in `src/devops_cli/core/process.py` checks `CONST_CODE_LOADING_ENV_PATTERNS` and `CONST_DATA_EGRESS_ENV_VARS`, and `src/devops_cli/config/constants.py` holds no pattern for the five keys.
- First check: run the reproduction command from #2750 to confirm the keys are accepted before the change.
- Second check: run `uv run devops ci test tests/core/test_process_env_guard.py` after the test is written.
- The devcontainer has no `go` and no `yarn`, so a live probe cannot run here. The change records the documented behavior and refuses the three keys. It adds no fake probe.

## Existing Tool Considered

No open maintained library covers a subprocess environment allowlist for this CLI. The existing guard in `src/devops_cli/core/process.py` is the tool. The change adds three patterns to `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py`. The written cost is about 200 tokens to add and keep, and no new code. It deletes no internal code.

# Proposal

## Why

#2747 reports that build_subprocess_env accepts three caller-provided keys that make a child write a file the caller names: PYTEST_ADDOPTS (pytest writes a JUnit file or loads a plugin) and npm_config_logs_dir / npm_config_cache (npm writes a log or cache file). The guard already refuses the same kind of key for other tools via CONST_CODE_LOADING_ENV_PATTERNS, but these three keys are absent, so a caller can direct a file write through them.

## What Changes

- Add "PYTEST_ADDOPTS" to CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py
- Add "NPM_CONFIG_*" to CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py
- Add test cases in tests/core/test_subprocess_env_boundary.py asserting SecurityError for PYTEST_ADDOPTS and NPM_CONFIG_* keys
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: Refuse PYTEST_ADDOPTS caller override, Refuse NPM_CONFIG family caller overrides

## Impact

- Code: `src/devops_cli/config/constants.py`
- Tests: `tests/core/test_subprocess_env_boundary.py`

## Feasibility

- The premise is confirmed against the inputs. src/devops_cli/core/process.py imports CONST_CODE_LOADING_ENV_PATTERNS from devops_cli.config.constants and passes it to _is_env_var_denied inside _is_env_override_refused. The issue body states PYTEST_ADDOPTS, npm_config_logs_dir and npm_config_cache are not in that constant, so they pass through. The reproduction command in the issue body confirms the gap: build_subprocess_env returns all three keys with no SecurityError.
- First checks the implementation runs: (1) uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(sorted(k for k in b(env={"PYTEST_ADDOPTS": "x", "npm_config_logs_dir": "x", "npm_config_cache": "x"}) if k in ("PYTEST_ADDOPTS", "npm_config_logs_dir", "npm_config_cache")))' to confirm the keys are refused after the fix; (2) uv run devops ci test tests/core/test_subprocess_env_boundary.py to confirm all guard tests pass.

## Existing Tool Considered

No open, maintained tool or library covers this need. The project builds its own guard in src/devops_cli/core/process.py. The written cost is 2 pattern entries and a comment in src/devops_cli/config/constants.py, plus 6 test cases in tests/core/test_subprocess_env_boundary.py. The cost to keep and fix is zero: the patterns are static and no update is needed until a new tool is added. The elapsed time to build is under 10 minutes. No internal code is deleted.

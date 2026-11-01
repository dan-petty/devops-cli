# Tasks

## 1. Add PYTEST_ADDOPTS and NPM_CONFIG_* to the guard

Reads: none. Changes: `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_boundary.py`.

- [ ] 1.1 Write a test that calls build_subprocess_env with env={"PYTEST_ADDOPTS": "--junitxml=/tmp/x.xml"} and asserts SecurityError is raised. Write a test that calls build_subprocess_env with env={"npm_config_logs_dir": "/tmp/logs"} and asserts SecurityError is raised. Write a test that calls build_subprocess_env with env={"npm_config_cache": "/tmp/cache"} and asserts SecurityError is raised. Write a test that calls build_subprocess_env with env={"NPM_CONFIG_REGISTRY": "https://example.com"} and asserts SecurityError is raised, confirming the family pattern covers any member, and verify that `uv run devops ci test tests/core/test_subprocess_env_boundary.py` fails on the base
- [ ] 1.2 Add the string "PYTEST_ADDOPTS" to the tuple CONST_CODE_LOADING_ENV_PATTERNS in src/devops_cli/config/constants.py, beside the existing entries. Add the string "NPM_CONFIG_*" to the same tuple. Add a comment noting that PYTEST_ADDOPTS lets pytest write a JUnit file or load a plugin, and NPM_CONFIG_* lets npm write a log or cache file into a caller-named directory, and verify that `uv run devops ci test tests/core/test_subprocess_env_boundary.py` passes
- [ ] 1.3 Change no document, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

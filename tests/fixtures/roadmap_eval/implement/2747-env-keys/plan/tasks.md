# Tasks

## 1. Refuse PYTEST_ADDOPTS and npm_config_logs_dir

Reads: `src/devops_cli/config/constants.py` (lines 1585 to 1720), `tests/core/test_subprocess_env_file_write.py`. Changes: `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_file_write.py`.

- [ ] 1.1 In `tests/core/test_subprocess_env_file_write.py`, add `PYTEST_ADDOPTS`, `npm_config_logs_dir` and `npm_config_logs-dir` to `REFUSED_FILE_WRITE_KEYS` with the probe in the comment above it (pytest 9.1.1 wrote the JUnit file, npm 11.19.1 wrote its debug log). Add `EXAMPLE_PYTEST_ADDOPTS` and `npm_config_logs_dirs` to the override of `test_a_key_that_only_contains_a_file_write_name_reaches_the_child`. Verify that `uv run devops ci test tests/core/test_subprocess_env_file_write.py` fails on the base: the refusal cases of the three new keys fail with `DID NOT RAISE`. The test of the ambient environment already passes on the base, because neither key is in the ambient allowlist, and it stays as a pin.
- [ ] 1.2 In `src/devops_cli/config/constants.py`, add `"PYTEST_ADDOPTS"` and `"NPM_CONFIG_LOGS[_-]DIR"` to `CONST_CODE_LOADING_ENV_PATTERNS`, in the block of the keys that make a child write a file (#2674). Extend the comment of the block with the two probes. In the comment of #2673, add `npm_config_cache` to the keys that stay accepted, with the reason that `devops install-tools` sets it. Verify that `uv run devops ci test tests/core/test_subprocess_env_file_write.py tests/core/test_subprocess_env_uv_npm.py tests/core/test_subprocess_env_boundary.py tests/commands/test_install_tools.py` passes. The last three files pin the keys that must stay accepted and the keys that stay refused.

## 2. Document the refused keys

Reads: `ARCHITECTURE.md` (the bullet "File-write child environment"). Changes: `ARCHITECTURE.md`.

- [ ] 2.1 In `ARCHITECTURE.md`, add `PYTEST_ADDOPTS` and `npm_config_logs_dir` to the bullet "File-write child environment", with what the probes showed. Say that `npm_config_cache` stays accepted because `devops install-tools` sets it, that npm writes its log below the cache directory, and that a caller that takes the path from an untrusted source must check it first. Verify that `git grep -n 'PYTEST_ADDOPTS' -- ARCHITECTURE.md` prints the bullet (it prints nothing on the base).
- [ ] 2.2 Verify that `uv run devops ci docs` passes. The change alters no command, option or message, so `uv run devops docs generate --sync-readme` has nothing to sync.

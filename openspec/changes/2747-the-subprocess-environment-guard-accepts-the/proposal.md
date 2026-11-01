# Proposal

## Why

Issue #2747: `build_subprocess_env` accepts a caller override of three keys that make a child write a file that the caller names. `PYTEST_ADDOPTS` makes pytest write a JUnit file. `npm_config_logs_dir` and `npm_config_cache` make npm write a debug log and cache files. The guard (`CONST_CODE_LOADING_ENV_PATTERNS`) already refuses the same kind of key for curl, git, Node.js and the glibc loader (#2674).

The refine block of the issue chose to refuse the whole `NPM_CONFIG_*` family. That choice cannot be built: `devops install-tools` sets five `npm_config_*` keys on purpose, and two existing tests pin them as accepted. This plan refuses the keys that a probe showed and that no caller sets. It names the key that stays accepted, and why. The issue asks for exactly this: "or the design of the guard names each such key that it accepts and the reason".

## What Changes

- `src/devops_cli/config/constants.py`: two entries join `CONST_CODE_LOADING_ENV_PATTERNS`, `PYTEST_ADDOPTS` and `NPM_CONFIG_LOGS[_-]DIR`. The comment of the entries names the probe. The comment of the accepted keys names `npm_config_cache`.
- `tests/core/test_subprocess_env_file_write.py`: the key tuple gets the new keys. The tests of that file then cover the refusal, the lower-case spelling, isolation on and off, and the ambient environment. The test of similar names gets two more keys.
- `ARCHITECTURE.md`: the "File-write child environment" bullet names the new keys and the key that stays accepted.
- The spec delta modifies three requirements of `subprocess-environment`. A refused key is a behavior that a consumer observes.
- The change does not refuse `npm_config_cache`, and it does not refuse the other `npm_config_*` keys. The design says why. No probe made a child write a file with another `npm_config_*` key, so the change claims none.
- The change fits one pull request: two groups, three files and one document.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the requirements "A caller override of a key that makes a child write a file that the caller names is refused", "An isolated child gets no file-write key from the environment" and "A key that only contains a refused name reaches the child".

## Impact

- Code: `src/devops_cli/config/constants.py`.
- Tests: `tests/core/test_subprocess_env_file_write.py`.
- Document: `ARCHITECTURE.md`.
- Callers that must keep working: `src/devops_cli/commands/install_tools.py` (line 311 sets `npm_config_cache`), `tests/core/test_subprocess_env_uv_npm.py` (`test_a_uv_or_npm_key_that_names_no_program_reaches_the_child`) and `tests/commands/test_install_tools.py` (the npm environment test). No caller in `src/` or `tests/` sets `PYTEST_ADDOPTS` or `npm_config_logs_dir`.

## Acceptance

The issue holds three requirements in its refine block.

| Criterion | Delivered by |
| :--- | :--- |
| `PYTEST_ADDOPTS` is refused. | Group 1. |
| The `npm_config_*` family is refused. | Group 1 refuses `npm_config_logs_dir`, the key that the probe showed and that no caller sets. The family is not refused, and `npm_config_cache` stays accepted: see the design. |
| Every key already in `CONST_CODE_LOADING_ENV_PATTERNS` stays refused. | Group 1. The tests of `tests/core/test_subprocess_env_file_write.py`, `tests/core/test_subprocess_env_uv_npm.py` and `tests/core/test_subprocess_env_boundary.py` keep passing. |

The issue also says that the fix must probe each key it claims. The Feasibility section holds the probe of each of the two refused keys. Group 2 records the result in `ARCHITECTURE.md`.

## Feasibility

Checked on `origin/main` at `9f3b7010` with pytest 9.1.1, npm 11.19.1 and node v24.22.2.

- The gap exists. `uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(sorted(k for k in b(env={"PYTEST_ADDOPTS": "x", "npm_config_logs_dir": "x", "npm_config_logs-dir": "x", "npm_config_cache": "x"}) if k in ("PYTEST_ADDOPTS", "npm_config_logs_dir", "npm_config_logs-dir", "npm_config_cache")))'` prints `['PYTEST_ADDOPTS', 'npm_config_cache', 'npm_config_logs-dir', 'npm_config_logs_dir']`. No `SecurityError`.
- The mechanism is as the issue says. `src/devops_cli/core/process.py` `_is_env_override_refused` upper-cases the key and tests it with `fnmatch.fnmatchcase` against `CONST_CODE_LOADING_ENV_PATTERNS`. `git grep -n 'PYTEST_ADDOPTS' src/devops_cli/config/constants.py` finds no pattern of that name, and the NPM entries there are the seven exact keys of #2673.
- Probe of `PYTEST_ADDOPTS`. In a temporary directory: `env -i PATH=<pytest dir>:/usr/bin:/bin HOME=<dir>/home PYTEST_ADDOPTS=--junitxml=<dir>/junit.xml pytest -q -p no:cacheprovider <one-test file>` printed `1 passed`. `<dir>/junit.xml` then held `<testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" ...`. The key makes pytest write a file at a path that the caller names. No probe loaded a plug-in with `-p`, so the plan does not claim it.
- Probe of `npm_config_logs_dir`. In a directory with an npm project file: `env -i ... npm_config_logs_dir=<dir>/logs npm ls` wrote `<dir>/logs/2026-11-01T13_54_59_102Z-debug-0.log`. The spelling `npm_config_logs-dir` wrote a log to its directory too, and so did `NPM_CONFIG_LOGS_DIR`. The guard upper-cases the key, so one pattern `NPM_CONFIG_LOGS[_-]DIR` covers all of them. The existing entries `NPM_CONFIG_SCRIPT[_-]SHELL`, `NPM_CONFIG_NODE[_-]OPTIONS` and `NPM_CONFIG_INIT[_-]MODULE` use the same form.
- Probe of `npm_config_cache`. `env -i ... npm_config_cache=<dir>/cache2 npm ls` wrote `<dir>/cache2/_update-notifier-last-checked` and `<dir>/cache2/_logs`. npm also writes its debug log below the cache directory when `npm_config_logs_dir` is unset.
- The family cannot be refused. `git grep -n 'npm_config' src/` finds `src/devops_cli/commands/install_tools.py` lines 311 to 315, where `install_npm_tool` passes `npm_config_cache`, `npm_config_userconfig`, `npm_config_globalconfig`, `npm_config_update_notifier` and `npm_config_loglevel` through `_run_installer` (line 251) to `run_subprocess` (`src/devops_cli/core/process.py` line 641, which calls `build_subprocess_env`). `fnmatch` of `NPM_CONFIG_*` matches all five keys, so the pattern of the refine block raises `SecurityError` in `devops install-tools`. Two tests pin these keys as accepted: `tests/core/test_subprocess_env_uv_npm.py` (`test_a_uv_or_npm_key_that_names_no_program_reaches_the_child`, which also pins `npm_config_git_tag_version` and `NPM_CONFIG_GITHUB`) and `tests/commands/test_install_tools.py` (the npm environment test, lines 462 to 500). The base spec requirement "A uv or npm key that names no program or that names a file reaches the child" pins them too.
- No caller sets the two refused keys. `git grep -n -i -E 'PYTEST_ADDOPTS|npm_config_logs' -- src tests .devcontainer .github Makefile` prints nothing, so no caller sets either key. The ambient environment is already filtered: neither key is in `DEFAULT_ALLOWED_ENV_VARS` or in `DEFAULT_ALLOWED_ENV_PREFIXES`, so an isolated child gets neither from the environment of the person. The new test pins this.
- Nothing newer did or removed this. `git log --oneline origin/main -S'PYTEST_ADDOPTS' -- src tests` and the same command with `-S'npm_config_logs'` print nothing, so no commit ever added or removed either name. `gh` search for `npm_config` and `PYTEST_ADDOPTS` finds #2673 and #2674 (both closed, merged), #2747 and its plan, and the plan #2162 (a mutation run that sets `PYTEST_ADDOPTS` in a shell command, not through `build_subprocess_env`).
- Dependency #2674 is merged: `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE` and `NODE_REDIRECT_WARNINGS` are in the tuple, and `tests/core/test_subprocess_env_file_write.py` exists.

## Existing Tool Considered

No open, maintained tool or library covers this need. The guard is two lists of `fnmatch` patterns over the standard library (`fnmatch`), in `src/devops_cli/core/process.py`. The change adds two entries to the list. Cost to build: about 8,000 tokens and 15 minutes. Cost to keep: none, the entries are static. Cost to fix: about 3,000 tokens each time a probe shows another key. The change deletes no internal code.

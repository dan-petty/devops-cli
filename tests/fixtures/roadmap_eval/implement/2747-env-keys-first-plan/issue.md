### Problem Description

`build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override that `CONST_CODE_LOADING_ENV_PATTERNS` matches. #2674 (pull request #2746) adds the keys that make `curl`, `git`, Python, Node.js and the glibc loader write a file that the caller names. The guard accepts more keys of the same kind in two other tools. A review of #2674 probed them with the real tools:

- `PYTEST_ADDOPTS` with the value `--junitxml=<path>`: pytest 9.1.1 wrote a JUnit file at the path. The key gives pytest any option, so it can also make pytest write other files or load a plug-in with `-p`.
- `npm_config_logs_dir`: npm wrote a debug log into the directory that the key names, when it ran `npm ls`.
- `npm_config_cache`: npm wrote a cache file into the directory that the key names, when it ran `npm ls`.

These keys belong with the keys of #2674 (keys that write a file) and with the keys of #2673 (the uv and npm keys that run a program). `npm_config_*` is a family: npm reads each npm setting from a key with this prefix, so the fix has to decide between the family and the single keys.

Not claimed: the reviewer did not reproduce `GNUTLS_KEYLOGFILE`, `PERLIO_DEBUG`, `MALLOC_TRACE` or `LOCPATH`. No probe ran for ruby, go, java, dotnet or cargo. The fix issue must probe each key it claims.

### Reproduction Steps

1. Run `uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(sorted(k for k in b(env={"PYTEST_ADDOPTS": "x", "npm_config_logs_dir": "x", "npm_config_cache": "x"}) if k in ("PYTEST_ADDOPTS", "npm_config_logs_dir", "npm_config_cache")))'`.
2. In a temporary directory `<dir>`, run `env -i PATH=<path> HOME=<dir> PYTEST_ADDOPTS=--junitxml=<dir>/junit.xml pytest <a test file in <dir>>`. Read `<dir>/junit.xml`.
3. Run `env -i PATH=<path> HOME=<dir> npm_config_logs_dir=<dir>/logs npm_config_cache=<dir>/cache npm ls` in a directory with a `package.json`. List `<dir>/logs` and `<dir>/cache`.

### Expected vs Actual Behavior

Expected: `build_subprocess_env` raises `SecurityError` for a caller override of a key that makes a child write a file that the caller names, or the design of the guard names each such key that it accepts and the reason.

Actual: step 1 returns all three keys with no `SecurityError`. Steps 2 and 3 show the files that the keys name.

### Environment Diagnostics

- DevOps CLI Version: main after #2738, with #2746 open
- OS & Architecture: Linux x86_64 (WSL2)
- Execution Environment: DevContainer

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate. #2673 asks for the uv and npm keys that run a program, and #2674 asks for the keys of other tools that write a file.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
The subprocess environment guard in build_subprocess_env accepts three caller-provided keys that make a child process write a file the caller names. PYTEST_ADDOPTS lets pytest write a JUnit file or load a plugin. npm_config_logs_dir and npm_config_cache let npm write a log or a cache file. The guard must refuse these keys, as it already refuses the keys of #2674.

### Acceptance criteria

### Requirement: Refuse PYTEST_ADDOPTS override
build_subprocess_env SHALL raise SecurityError when a caller override sets PYTEST_ADDOPTS.

#### Scenario: Caller sets PYTEST_ADDOPTS
- **WHEN** A caller passes PYTEST_ADDOPTS in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

### Requirement: Refuse npm_config family overrides
build_subprocess_env SHALL raise SecurityError when a caller override sets any key matching the npm_config_* family.

#### Scenario: Caller sets npm_config_logs_dir
- **WHEN** A caller passes npm_config_logs_dir in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

### Requirement: Existing refusals unchanged
build_subprocess_env SHALL continue to raise SecurityError for every key already in CONST_CODE_LOADING_ENV_PATTERNS.

#### Scenario: Caller sets LD_PRELOAD
- **WHEN** A caller passes LD_PRELOAD in the env dict to build_subprocess_env
- **THEN** build_subprocess_env raises SecurityError

### Existing Tool Considered
No check has run. No open, maintained tool or library covers this need. The project builds its own guard in src/devops_cli/core/process.py. The written cost is 3 pattern entries and a comment in src/devops_cli/config/constants.py, plus 6 test cases in tests/test_subprocess_env_boundary.py. The cost to keep and fix is zero: the patterns are static and no update is needed until a new tool is added. The elapsed time to build is under 10 minutes.

### Key questions
- **Does the npm fix deny the npm_config_* family or only the two probed keys?**: Deny the family with the pattern NPM_CONFIG_*. The existing guard already uses family patterns for dangerous families: DYLD_* and BASH_FUNC_*. The issue states that npm reads each npm setting from a key with this prefix, so any member of the family can direct a file write. A single-key list would miss future or unprobed members. (best practice) [sources: src/devops_cli/core/process.py, openspec/changes/archive/2026-10-28-2205-refuse-code-loading-env-keys/design.md]
  - Chosen: Deny the NPM_CONFIG_* family. Consistent with the existing DYLD_* and BASH_FUNC_* family patterns. npm reads every setting from a key with this prefix, so any member can direct a file write. A single-key list would miss unprobed members.
  - Rejected: Deny only npm_config_logs_dir and npm_config_cache. Narrower scope, but npm's config system is open-ended. A future or unprobed npm_config_* key could also direct a file write. The existing design uses family patterns for this case.
- **Is PYTEST_ADDOPTS a code-loading key, a file-writing key, or both?**: Both. The value --junitxml= makes pytest write a JUnit file. The value -p  makes pytest load a plugin, which runs code. The guard refuses it under the same constant as the other keys. [sources: src/devops_cli/core/process.py]
- **Must the fix probe each key it claims before adding it to the guard?**: Yes. The issue states: 'The fix issue must probe each key it claims.' The reviewer probed PYTEST_ADDOPTS, npm_config_logs_dir and npm_config_cache with the real tools. The implementation must include a probe for each key it adds. [sources: src/devops_cli/core/process.py]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
#2674
<!-- devops-roadmap-refine:end -->

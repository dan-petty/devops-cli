# Proposal

## Why

Issue #2205: the subprocess environment guard refuses only six keys that make a child load or run code that its caller did not choose.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override of `LD_PRELOAD`, `LD_LIBRARY_PATH`, `DYLD_INSERT_LIBRARIES`, `DYLD_LIBRARY_PATH`, `BASH_ENV` or `ENV`. The set is a local variable of the function.
- The guard accepts other keys of the same families. glibc loads each object that `LD_AUDIT` names into the child. The macOS loader reads more `DYLD_` keys, for example `DYLD_FRAMEWORK_PATH` and `DYLD_FALLBACK_LIBRARY_PATH`. A bash child defines a function from each `BASH_FUNC_<name>%%` key, and that function replaces a command of the same name.
- `run_rule_pack_tests` in `src/devops_cli/review/rules_pack.py` gives Semgrep the full ambient environment as its override (`{**os.environ, ...}`). Thus the guard checks every ambient key of that call. On a host where bash exports a function, such as `which` on Fedora and RHEL, the wider guard refuses `devops review rules test`. The full copy also gives Semgrep the credentials that `build_subprocess_env` removes from the environment of a child.

## What Changes

- The constant `CONST_CODE_LOADING_ENV_PATTERNS` in `src/devops_cli/config/constants.py` holds the refused key families as `fnmatch` patterns: `LD_AUDIT`, `LD_LIBRARY_PATH`, `LD_ORIGIN_PATH`, `LD_PRELOAD`, `DYLD_*`, `BASH_ENV`, `ENV` and `BASH_FUNC_*`. Its comment names the sources: glibc `ld.so(8)`, macOS `dyld(1)` and the function export of bash.
- `build_subprocess_env` matches the upper-case key of each caller override against that constant, with the same `fnmatchcase` helper that it uses for the credential patterns. A match raises the same `SecurityError` and error code as before. The local set in the function is deleted.
- `run_rule_pack_tests` gives Semgrep only its own override, `SEMGREP_ENABLE_VERSION_CHECK=0`. `build_subprocess_env` gives the rest of the environment, without credentials.
- `ARCHITECTURE.md` describes the guard in its section on safe subprocess execution.
- A caller override that the guard refuses is a message that a consumer sees, so the change carries a spec delta: the new capability `subprocess-environment`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `subprocess-environment`: which caller overrides of a child environment devops-cli refuses, and what a refusal reports.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`, `src/devops_cli/review/rules_pack.py`.
- `tests/test_subprocess_env_boundary.py`, `tests/test_review_rules_pack.py`.
- `ARCHITECTURE.md`.

## Feasibility

- The guard accepts the keys today. On `origin/main` at `bb46660c`, `build_subprocess_env(env={key: "x"})` returned the key for `LD_AUDIT`, `ld_audit`, `DYLD_FRAMEWORK_PATH`, `DYLD_FALLBACK_LIBRARY_PATH`, `DYLD_FALLBACK_FRAMEWORK_PATH` and `BASH_FUNC_x%%`, and raised `SecurityError` for `LD_PRELOAD`.
- glibc 2.43 (Debian 2.43-7) loads the object that `LD_AUDIT` names: `LD_AUDIT=/nonexistent/libaudit.so /bin/true` printed "ERROR: ld.so: object '/nonexistent/libaudit.so' cannot be loaded as audit interface". The `ld.so(8)` page of that system says that `LD_AUDIT` and `LD_PRELOAD` name objects to load, and that `LD_LIBRARY_PATH` names the directories to search. It says that `LD_ORIGIN_PATH` is the "Path where the binary is found". The glibc source (`sysdeps/unix/sysv/linux/dl-origin.c`) uses that value for `$ORIGIN` when `/proc/self/exe` cannot be read.
- bash 5.3.15 writes `export -f f` as the environment key `BASH_FUNC_f%%`. `env 'BASH_FUNC_git%%=() { echo "function ran instead of git"; }' bash -c 'git --version'` printed "function ran instead of git". `bash(1)` says that bash reads the file that `BASH_ENV` names before a script, and `ENV` in posix mode.
- The `dyld(1)` page of Apple (`apple-oss-distributions/dyld`, `doc/man/man1/dyld.1`) documents 20 variables, and all start with `DYLD_`. Among them, `DYLD_FRAMEWORK_PATH`, `DYLD_FALLBACK_FRAMEWORK_PATH`, `DYLD_FALLBACK_LIBRARY_PATH`, `DYLD_VERSIONED_LIBRARY_PATH`, `DYLD_VERSIONED_FRAMEWORK_PATH` and `DYLD_IMAGE_SUFFIX` select the code that loads. This system has no macOS loader, so the change cites the page and does not run it.
- `src/devops_cli/review/rules_pack.py` line 236 passes `{**os.environ, "SEMGREP_ENABLE_VERSION_CHECK": "0"}` as `env` to `run_subprocess`, which gives it to `build_subprocess_env` as the caller override.

## Existing Tool Considered

The family list is a closed domain that three manual pages define, so the change uses no parser. The match uses `fnmatch.fnmatchcase` of the standard library, as the credential patterns of the same module do. No maintained library publishes the set of environment keys that load code. The change deletes the local set `dangerous_env_keys` in `build_subprocess_env` and the full copy of the environment in `run_rule_pack_tests`.

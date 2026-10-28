# Design

## Decisions

- **One constant of `fnmatch` patterns.** `CONST_CODE_LOADING_ENV_PATTERNS` holds exact names (`LD_AUDIT`, `ENV`) and family patterns (`DYLD_*`, `BASH_FUNC_*`) in one tuple. `build_subprocess_env` already matches the credential patterns with `_is_env_var_denied`, which runs `fnmatch.fnmatchcase` on the upper-case key. The guard calls the same helper with the new constant, so one rule matches both kinds of entry and the case of the key has no effect.
- **The constant is in `config/constants.py`.** CONTRIBUTING.md says to declare each tuple that matches or filters values there, with the `CONST_` prefix. The issue proposed `src/devops_cli/core/process.py`, but the project rule decides. The constant is not a tunable value, so it is not in `config/defaults.py`.
- **The glibc keys are the four that choose which code loads.** `ld.so(8)` says that `LD_PRELOAD` and `LD_AUDIT` name objects to load and that `LD_LIBRARY_PATH` names the directories to search. `LD_ORIGIN_PATH` sets `$ORIGIN`, which the loader expands in the run path of a binary, in `LD_LIBRARY_PATH`, in `LD_PRELOAD` and in `LD_AUDIT`. glibc uses it when `/proc/self/exe` cannot be read (`sysdeps/unix/sysv/linux/dl-origin.c`). It thus chooses the library directory in a child that has no `/proc`.
- **Every `DYLD_` key.** All 20 variables of `dyld(1)` start with `DYLD_`. Most of them choose the code that loads. The others only print diagnostics. A pattern for the family also covers a key that a later macOS adds.
- **Every `BASH_FUNC_` key.** bash 5.3 writes `export -f <name>` as `BASH_FUNC_<name>%%`. Earlier patched forms of bash 4.3 used other suffixes. The pattern `BASH_FUNC_*` covers each suffix.
- **The Semgrep call gives only its own key.** `run_rule_pack_tests` gave `{**os.environ, "SEMGREP_ENABLE_VERSION_CHECK": "0"}` as the override. The guard checks each override key, so an exported bash function in the environment of the person stopped the call. The call now gives only `SEMGREP_ENABLE_VERSION_CHECK`. `semgrep 1.179.0 --version` and `semgrep --test --metrics off src/devops_cli/review/rules` passed with the environment that `build_subprocess_env` builds, which holds `PATH`, `HOME` and the other allowed keys and no credential.

## Rejected alternatives

- **Two constants: a set of exact keys and a tuple of prefixes.** The issue asks for one constant. Two constants need two match rules. The credential patterns of the same module show that one `fnmatch` tuple holds both kinds.
- **Refuse every `LD_` key.** `ld.so(8)` lists keys that do not load code, for example `LD_BIND_NOW`, `LD_DEBUG` and `LD_WARN`. They change the output or the time of symbol binding. `LD_PROFILE` names an object that is already loaded, and `LD_DEBUG_OUTPUT` and `LD_PROFILE_OUTPUT` name output files. The issue asks for the keys that load code.
- **Refuse the keys in the ambient environment too.** With `isolate_env=True`, the allowlist already removes every key of these families from the ambient environment. With `isolate_env=False`, the caller asks for the environment of the person as it is, and the person chose it.
- **Accept an override when its value is the same as the ambient value.** This keeps the full copy of the environment in `run_rule_pack_tests`, and the copy also gives Semgrep the credentials of the person. The cause is the full copy, so the change removes it.

## Non-goals

- Keys outside the loader and shell families that also load code, for example `GCONV_PATH` of glibc `iconv`, `PYTHONPATH`, `PERL5LIB` and `NODE_OPTIONS`. The issue limits the guard to the families of `ld.so(8)`, `dyld(1)` and bash.

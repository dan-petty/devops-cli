# Design

## Decisions

- **The sources are the manual pages and probes.** `curl(1)` names `SSLKEYLOGFILE` and `QLOGDIR`, `node(1)` names `NODE_V8_COVERAGE` and `NODE_REDIRECT_WARNINGS`, and `ld.so(8)` names the `LD_` keys. A probe confirmed each refused key (proposal, Feasibility), and says which file the child wrote.
- **The new names sit in the constant that exists.** The constant `CONST_CODE_LOADING_ENV_PATTERNS` already holds `GIT_TRACE`, `GIT_TRACE2` and `GIT_TRACE_CURL` through the `GIT_*` pattern, which write a file and load no code. One list of refused keys keeps one check in `_is_env_override_refused`. A second constant would need a second check for the same result. The constant is not renamed: the names of the constant and of its comment keep the history of #2205. The comment of the new block says what the keys do.
- **`LD_*` replaces the four `LD_` names.** The sudo `env_delete` table lists `LD_*`, and the guard already refuses each `DYLD_`, `GIT_` and `SSH_` key. glibc reads more `LD_` keys than the four loader keys and the two output keys. No file of the code base sets an `LD_` key, and no `LD_` key is in `DEFAULT_ALLOWED_ENV_VARS`. A pattern also refuses a key that a later glibc adds. Only the output keys, `LD_DEBUG` and `LD_PROFILE` ran in a probe, and the other `LD_` keys are refused as the family, not as a claim that they write a file.
- **Both trigger keys are refused.** `LD_DEBUG_OUTPUT` has an effect only with `LD_DEBUG`, and `LD_PROFILE_OUTPUT` only with `LD_PROFILE`. The pattern covers both pairs, so a caller cannot set the trigger and leave the output key to the environment.
- **An isolated child gets none of the keys from the environment.** `*KEY*` is a denied pattern, so `SSLKEYLOGFILE` never passes the filter. `QLOGDIR`, `NODE_V8_COVERAGE`, `NODE_REDIRECT_WARNINGS` and the `LD_` keys are in no allowed list. No change of the filter is needed, and a test pins the result.
- **The spec change only adds requirements,** and the tests are in `tests/test_subprocess_env_file_write.py`, so that the work of #2673 on the neighbouring test file and constant block merges without conflict.

## Rejected alternatives

- **A new constant `CONST_FILE_WRITING_ENV_PATTERNS`.** It needs a second matcher and a second call in `_is_env_override_refused`. The refusal is the same, so one list and one check are simpler.
- **Refuse only the four named `LD_` keys.** A later glibc key, or a trigger key, stays open. The family is the rule for `DYLD_`, `GIT_` and `SSH_`.
- **Refuse `PYTHONDUMPREFSFILE` and `GPGRT_TRACE_FILE`.** No probe made a child write a file with either key (proposal, Feasibility). A claim without a probe is a guess, and the constant would hold two names that do nothing in the tools that run here.
- **Check the value of the key.** The value is a path, and another path or key passes such a check.

## Keys considered and not claimed

- `PYTHONDUMPREFSFILE`: only a Python build with `Py_TRACE_REFS` can write the file. The interpreters of the project have it off.
- `GPGRT_TRACE_FILE`: the string is in `libgpg-error`, but no `gpg` command wrote a file with it.
- `LESS` (#2735) and `GH_TELEMETRY_ENDPOINT_URL` (#2739): the issues for them are open, and they are outside this change.

## Non-goals

- The library keys that load a module: #2503.
- The keys of `uv` and `npm` that run a program: #2673.

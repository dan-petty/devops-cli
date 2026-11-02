# Design

## Probe results

One result for each key of #2750. The proposal holds the commands and the output.

| Key | Result | Status |
| :--- | :--- | :--- |
| `GOFLAGS` | go 1.24.7 ran the marker as `-toolexec` for each compile step. | Refused |
| `YARN_YARN_PATH` | Yarn 1.22.22 ignored it. A reading of Yarn 4.9.2 shows that it reads the key and runs the file. No live run of Yarn 4 here. | Refused |
| `UV_ENV_FILE` | uv 0.11.32 does not read its own keys from the file. It puts the keys of the file, `LD_PRELOAD`, `NODE_OPTIONS` and `PYTHONSTARTUP`, into the program that `uv run` starts. | Refused |
| `UV_TOOL_DIR` | `uv tool run` and `uvx` started the executable of a tool environment in the directory. | Refused |
| `npm_config_cache` | `npx` started the `bin` script of a package from a cache that the caller prepared. | Accepted |

## Decisions

- **Refuse `UV_TOOL_DIR` although #2750 says to document it.** The probe shows that uv starts a program from the directory, the same mechanism as `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT`, which #2673 refuses. The criterion of the issue is "a key that makes the tool start a program that the caller names is refused". No file of the repository sets the key (`git grep -n UV_TOOL_DIR -- src tests` prints nothing), so the refusal breaks no caller.
- **Refuse `UV_ENV_FILE` for the right reason.** The file loads keys. It does not run. The refusal still holds, because the file can put `LD_PRELOAD`, `NODE_OPTIONS` or `PYTHONSTARTUP` into the program that `uv run` starts, and `build_subprocess_env` refuses all three from a caller. A caller that passes `UV_ENV_FILE` skips the guard for these keys. The text of `ARCHITECTURE.md` says this, not the "sources" of the issue.
- **Refuse `GOFLAGS` and `YARN_YARN_PATH` as exact entries.** go reads one key for its flags, and Yarn 4 maps the setting `yarnPath` to this one key. A pattern such as `YARN_*` would also refuse `YARN_ENABLE_TELEMETRY` and `YARN_NPM_REGISTRY_SERVER`, which no probe made dangerous. The guard keeps one exact entry for each probed key, as for `PYTEST_ADDOPTS` (#2747).
- **Refuse `YARN_YARN_PATH` without a live run of Yarn 4.** The key costs nothing to refuse: devops-cli starts no `yarn` (`git grep -n '"yarn"' -- src` prints nothing). The page of Yarn documents `yarnPath`, and the bundle of Yarn 4.9.2 runs the file with `execFileSync`. The workflow follow-up asks a person for the live run.
- **Keep `npm_config_cache` accepted.** The probe shows that a prepared cache makes `npx` start a program. But `devops install-tools` sets the key (`src/devops_cli/commands/install_tools.py` line 311) and runs `npm ci`, which starts no cached package. A refusal stops the installer and breaks `tests/commands/test_install_tools.py`. #2747 decided the same for the file-write effect. A caller that takes the cache path from an untrusted source must check the path first, and a caller must not run `npx` with a cache that it does not control. `ARCHITECTURE.md` says so.
- **Put the four entries in `CONST_CODE_LOADING_ENV_PATTERNS`.** `_is_env_override_refused` reads this tuple for a caller override, with isolation on and off. No new guard function is needed.
- **Also put `UV_TOOL_DIR` and `UV_ENV_FILE` in `DEFAULT_DENIED_ENV_PATTERNS`.** The scratch run shows that `build_subprocess_env()` passes both from the environment of the person to an isolated child, because the prefix `UV_` allows them. The requirement "An isolated child gets no refused key from the environment" has exactly two uv exceptions, `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR`, which the gate of a CI runner needs (#1735). No file needs these two keys, so the change adds no exception. It follows `UV_PROJECT_ENVIRONMENT` (#2673). `GOFLAGS` and `YARN_YARN_PATH` need no entry there: no allowed variable or prefix matches them.
- **Test in two files.** The two uv keys join `REFUSED_UV_NPM_KEYS` in `tests/core/test_subprocess_env_uv_npm.py`, so the refusal test (isolation on and off, each case, the message and the error code) covers them. The Go and Yarn keys get `tests/core/test_subprocess_env_go_yarn.py`, one file for each tool family as for #2672 (gh and kubectl), #2673 and #2674. Both files are in the mirror directory of `src/devops_cli/core/process.py`.
- **Modify one requirement and add two.** The uv and npm refusal requirement lists keys, so it is modified with a new scenario. The Go and Yarn refusal and the ambient drop of the four keys have no existing requirement name. The requirement "A uv or npm key that names no program or that names a file reaches the child" pins `npm_config_cache` and does not change.

## Security question

Does a refusal of the four keys close a way to run code through the guard, and does it harm a caller?

- A caller override of any of the four keys is refused with `SecurityError`, with isolation on and off. The test asserts the message and `SECURITY_ERROR` for each case.
- The environment of the person is a second path. With isolation on, the change drops `UV_TOOL_DIR` and `UV_ENV_FILE`. A person who exports one of them now sees an isolated child use the default tool directory and read no `.env` file. This is a change for a person, and the plan makes it on purpose: an env file can carry credentials that isolation exists to drop. A person must confirm it (workflow follow-up). With isolation off the child gets the environment as it is, as the spec says.
- The refusal does not stop a tool from reading a file in the working tree. `.yarnrc` with `yarn-path` ran the marker in Yarn 1 (see the probe). The guard handles environment keys only.
- Left unprobed on purpose: `GOROOT`, `CC` and `GOTOOLCHAIN` for go, `YARN_INJECT_ENVIRONMENT_FILES` for Yarn 4 (the bundle shows the setting `injectEnvironmentFiles`, the same mechanism as `UV_ENV_FILE`) and `UV_TOOL_BIN_DIR`. They are not keys of #2750. A person can file them.
- No secret reaches a log or a message: the refusal message holds the key name and no value.

## Rejected alternatives

- **Document `UV_TOOL_DIR` and `npm_config_cache` as safe (the choice of the refine block).** The probe makes a program start for both keys. A text that calls them safe would be false.
- **Refuse `npm_config_cache` and make `install_npm_tool` pass `--cache` as an argument.** It changes the installer and its test to satisfy the guard. The key makes `npx` start a program only when the caller runs `npx` with a cache that it did not prepare, and `devops` runs no `npx` (`git grep -n '"npx"' -- src` prints nothing).
- **Refuse the keys `GO*` and `YARN_*` by pattern.** `GOPATH` and `GOCACHE` name directories, the request of golangci-lint sets `GOTOOLCHAIN=local` (`openspec/specs/review-tool-sandbox/spec.md` line 192), and `YARN_ENABLE_TELEMETRY` is not code. A pattern refuses keys that no probe made dangerous and that a later caller may need.
- **Keep `UV_ENV_FILE` accepted and document the risk.** A file with `LD_PRELOAD` skips the guard for the child program. A document does not stop a caller that takes the path from an untrusted source.
- **Drop the keys from the environment of the person only.** A caller override would still reach the child, which is the case of #2750.
- **Add a live probe test.** A test doubles only edges, and every program is an edge (`docs/TESTING.md` line 67), so a test cannot start the real tool. The probe belongs in the design, as for #2673.

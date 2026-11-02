# Proposal

## Why

Issue #2750: the subprocess guard `build_subprocess_env` accepts five keys that no probe covered. The changes for #2672, #2673, #2674 and #2747 refuse the keys that a probe showed to make a child run a program or write a file. This change probes the five keys of #2750 and refuses each one that the probe, or the documentation of the tool, shows to be dangerous.

The probes changed two claims of the issue:

- `UV_TOOL_DIR` is not safe. The issue and its refine block say it names a directory that starts no program. The probe shows that `uv tool run` starts the executable of a tool environment in that directory. So the plan refuses it, as the guard already refuses `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT`.
- `UV_ENV_FILE` does not make uv run the file. The issue says "a file that uv sources, which can execute code". `uv run --help` says "Load environment variables from a `.env` file". The real risk is that the file puts keys that the guard refuses (`LD_PRELOAD`, `NODE_OPTIONS`, `PYTHONSTARTUP`) into the program that `uv run` starts. The probe shows this.

## What Changes

- `src/devops_cli/config/constants.py`: four entries join `CONST_CODE_LOADING_ENV_PATTERNS`: `GOFLAGS`, `YARN_YARN_PATH`, `UV_TOOL_DIR` and `UV_ENV_FILE`. The comment of the entries names each probe.
- `src/devops_cli/core/process.py`: `UV_TOOL_DIR` and `UV_ENV_FILE` join `DEFAULT_DENIED_ENV_PATTERNS`, as `UV_PROJECT_ENVIRONMENT` does. The prefix `UV_` would pass both keys from the environment of the person to an isolated child.
- `tests/core/test_subprocess_env_go_yarn.py` (new): the cases for `GOFLAGS` and `YARN_YARN_PATH`.
- `tests/core/test_subprocess_env_uv_npm.py`: the cases for `UV_TOOL_DIR` and `UV_ENV_FILE`.
- `ARCHITECTURE.md`: the bullet "Uv and npm child environment" names the two uv keys and the corrected reason for `UV_ENV_FILE`. A new bullet "Go and Yarn child environment" names the two other keys. The bullet "File-write child environment" gets the result of the `npm_config_cache` probe.
- `npm_config_cache` stays accepted. The design gives the probe result and the reason.
- The spec delta modifies one requirement of `subprocess-environment` and adds two. A refused key is a behavior that a consumer observes.
- The change fits one pull request: three groups, two source files, two test files and one document.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `subprocess-environment`: the requirement "A caller override of a key that makes uv or npm run a program is refused" is modified. The requirements "A caller override of a key that makes go or yarn run a program is refused" and "An isolated child gets no Go, Yarn, UV_TOOL_DIR and UV_ENV_FILE key from the environment" are added.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/core/process.py`.
- Tests: `tests/core/test_subprocess_env_go_yarn.py` (new), `tests/core/test_subprocess_env_uv_npm.py`.
- Document: `ARCHITECTURE.md`.
- Callers that must keep working: `src/devops_cli/commands/install_tools.py` (line 311 sets `npm_config_cache` for `npm ci`), `src/devops_cli/commands/devcontainer.py` (line 699) and `src/devops_cli/devcontainer/devcontainer_plans.py` (line 135) run `uv tool install pre-commit` and set no uv key, and `src/devops_cli/security/golangci_lint.py` (line 194) sets no `GOFLAGS`. Tests that pin them: `tests/commands/test_install_tools.py`, `tests/security/test_golangci_lint_scanner.py` (line 257) and `test_a_uv_or_npm_key_that_names_no_program_reaches_the_child` in `tests/core/test_subprocess_env_uv_npm.py`.
- Left on purpose: `openspec/specs/review-tool-sandbox/spec.md` (lines 192 and 198) says the golangci-lint request sets no `GOFLAGS`. That requirement is about a sandbox request and stays true.

## Dependencies

None. The search of open issues and pull requests for `2750`, `GOFLAGS`, `YARN_YARN_PATH`, `UV_ENV_FILE`, `UV_TOOL_DIR` and `build_subprocess_env` finds only #2750 and this plan (#3165). The earlier changes are merged: #2672 (gh and kubectl), #2673 (uv and npm), #2674 (file-write keys) and #2747 (`PYTEST_ADDOPTS`, `npm_config_logs_dir`). The comments of #2750 hold only the intake and refine notes.

## Acceptance

The refine block of #2750 holds five requirements. The body that a person wrote has no `Acceptance criteria` list.

| Requirement of the refine block | Delivered by |
| :--- | :--- |
| Probe result recorded for each of the five keys | The design holds one result for each key. Group 3 copies the results to `ARCHITECTURE.md`. |
| `GOFLAGS` refused | Group 1. |
| `YARN_YARN_PATH` refused | Group 1. |
| `UV_ENV_FILE` refused | Group 1. |
| `UV_TOOL_DIR` documented | Changed by the probe: Group 1 refuses it, because the probe shows that uv starts a program from it. The design gives the reason. |
| `npm_config_cache` documented | The design and group 3. The key stays accepted. |

## Feasibility

Checked on `origin/main` at `ff9ad065` with uv 0.11.32, npm 10.9.9, node v22, go 1.24.7 and yarn 1.22.22, in a plain clone. Every probe ran with `env -i`, a temporary `HOME`, a marker program that appends a line to a file, and a control run without the key. No probe used the network, except the one for `npm_config_cache`, which used a short-lived server on `127.0.0.1` to fill a cache.

- The gap exists. `uv run python -c 'from devops_cli.core.process import build_subprocess_env as b; print(sorted(b(env={"GOFLAGS": "x", "YARN_YARN_PATH": "x", "UV_ENV_FILE": "x", "UV_TOOL_DIR": "x"})))'` prints a list that holds `GOFLAGS`, `UV_ENV_FILE`, `UV_TOOL_DIR` and `YARN_YARN_PATH`. No `SecurityError`.
- The mechanism is as `process.py` says. `_is_env_override_refused` (line 147) tests the upper-case key against `CONST_CODE_LOADING_ENV_PATTERNS` with `fnmatch.fnmatchcase`. `git grep -n -E 'GOFLAGS|YARN_YARN_PATH|UV_ENV_FILE|UV_TOOL_DIR' -- src tests ARCHITECTURE.md README.md` finds only `golangci_lint.py:194` (a comment that sets no `GOFLAGS`) and `tests/security/test_golangci_lint_scanner.py:234,257`. No code sets the four keys.
- The environment of the person. With the four keys set in `os.environ`, `build_subprocess_env()` returns `['UV_ENV_FILE', 'UV_TOOL_DIR']` with isolation on, and all four with isolation off. The prefix `UV_` passes the two uv keys. `GOFLAGS` and `YARN_YARN_PATH` match no allowed variable or prefix.
- Apply check. A scratch copy of the change (four entries in the first tuple, two in the second) made `build_subprocess_env(env={k: "x"})` raise `SecurityError` for `GOFLAGS`, `goflags`, `YARN_YARN_PATH`, `UV_ENV_FILE` and `UV_TOOL_DIR`, and accept `EXAMPLE_GOFLAGS`. `pytest` of `tests/core/test_subprocess_env_uv_npm.py`, `_boundary.py`, `_file_write.py`, `_gh_kubectl.py`, `tests/commands/test_install_tools.py` and `tests/security/test_golangci_lint_scanner.py` gave 743 passed and 1 failed. The failed test, `test_gh_auth_gets_a_token_its_caller_passes`, fails the same way on the base, because the sandbox injects a proxy token. The scratch copy was reverted.
- Probe of `GOFLAGS`. go 1.24.7. In a module with an empty `main`, `GOFLAGS=-toolexec=<dir>/bin/marker go build .` ran the marker for each compile step: the file held `marker ran: .../pkg/tool/linux_amd64/compile`. The control run (no `GOFLAGS`, empty build cache) left no marker. `go help build` documents `-toolexec 'cmd args'`.
- Probe of `YARN_YARN_PATH` with Yarn 1.22.22: `YARN_YARN_PATH`, `yarn_yarn_path` and `npm_config_yarn_path` each left no marker, the same as the control run. A `.yarnrc` file with `yarn-path "<dir>/bin/fakeyarn.cjs"` in the project ran the marker. So Yarn 1 reads the setting from a file only, and the key is harmless there.
- Reading of Yarn 4.9.2 (`npm pack @yarnpkg/cli-dist@4.9.2`, read as text, not run). The bundle holds the environment prefix `mT="yarn_"`, the setting `yarnPath:{description:"Path to the local executable that must be used over the global one",type:"ABSOLUTE_PATH"}`, the call `f.useWithSource("<environment>",P(c),...)` where `P` keeps `yarnPath`, `ignorePath` and `injectEnvironmentFiles`, and `execFileSync(process.execPath,[ue.fromPortablePath(r),...e],s)` for the path. So Yarn 4 reads `YARN_YARN_PATH` from the environment and runs the file. This is the documented `yarnPath` of Yarn 4. The live run of Yarn 4 did not happen here: the sandbox refused to run code that was downloaded from npm. The workflow follow-up asks a person to run it.
- Probe of `UV_ENV_FILE`. `uv run --help` prints "--env-file <ENV_FILE> Load environment variables from a `.env` file [env: UV_ENV_FILE=]". With `UV_ENV_FILE` naming a file that holds `UV_PYTHON=<dir>/bin/markerpy`, `uv run --no-project python -c 'print("ran")'` left no marker, while `UV_PYTHON=<dir>/bin/markerpy` in the environment left the marker (the #2673 result). So the file does not set the keys of uv. With a file that holds `LD_PRELOAD=/opt/example/evil.so`, `uv run sh -c 'echo $LD_PRELOAD'` printed `LD_PRELOAD=/opt/example/evil.so`, and the loader printed `ERROR: ld.so: object '/opt/example/evil.so' from LD_PRELOAD cannot be preloaded`. With `NODE_OPTIONS="--require /opt/example/evil.js"` and `PYTHONSTARTUP=/opt/example/evil.py` in the file, the child printed both values. The control run printed empty values. The file puts refused keys into the child program.
- Probe of `UV_TOOL_DIR`. A tool environment `example-tool` (made with `uv venv`, a `dist-info` with `METADATA` and a `RECORD` line for `bin/example-tool`, a `uv-receipt.toml`, and a marker script as `bin/example-tool`) in a directory. `UV_TOOL_DIR=<dir> uv tool run --offline example-tool` and `uvx --offline example-tool` each left `marker ran: example-tool from the tool dir`. Without the key, `uv tool run --offline example-tool` printed "No solution found" and ran nothing. The key makes uv start a program from a directory that the caller names.
- Probe of `npm_config_cache`. A package `example-pkg` with a `bin` script that writes a marker. Step 1 filled a cache: `npm_config_cache=<dir>/evilcache npm_config_registry=http://127.0.0.1:18750 npx --yes example-pkg` against a local server, which stopped before the next step. Step 2: `npm_config_cache=<dir>/evilcache npm_config_offline=true npm_config_registry=http://127.0.0.1:18750 npx --yes example-pkg` with no server left `marker ran: example-pkg cli.js`. The control run with the default cache failed with `ENOTCACHED` and left no marker. So a cache directory that the caller prepared makes `npx` start a program. `devops install-tools` sets this key (`install_tools.py:311`) and runs `npm ci`, not `npx`.
- Nothing newer did this work. `git log --oneline origin/main -S<key> -- src tests` prints nothing for `UV_ENV_FILE`, `UV_TOOL_DIR` and `YARN_YARN_PATH`. For `GOFLAGS` it prints only the root commit `36da9390` of the clone, which holds the comment of `golangci_lint.py`. The open issues and pull requests that name the keys are #2750 and this plan only (see Dependencies). The merged #3213 and #3195 do not touch the guard.

## Existing Tool Considered

No open, maintained library lists the environment keys that start a program for each tool. The need is a list of `fnmatch` patterns over the standard library, as the guard already has in `CONST_CODE_LOADING_ENV_PATTERNS`. The sources are the help pages of each tool and the probes above. The change adds four entries and two entries to existing lists, and deletes no code. Cost to build: about 12,000 tokens (tests, six entries, one document, six probes) and about 40 minutes. Cost to keep: none, the entries are static. Cost to fix: about 3,000 tokens and 10 minutes each time a probe shows another key.

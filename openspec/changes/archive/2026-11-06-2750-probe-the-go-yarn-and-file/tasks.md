# Tasks

## 1. Refuse the four keys from a caller

Reads: `src/devops_cli/core/process.py`, `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_uv_npm.py`, `tests/core/test_subprocess_env_file_write.py`. Changes: `src/devops_cli/config/constants.py`, `tests/core/test_subprocess_env_uv_npm.py`, `tests/core/test_subprocess_env_go_yarn.py` (new).

- [x] 1.1 Write the failing tests. In `tests/core/test_subprocess_env_uv_npm.py`, add `UV_TOOL_DIR` and `UV_ENV_FILE` to `REFUSED_UV_NPM_KEYS`, with the probe in the comment above it (uv 0.11.32: `uv tool run` started the executable of a tool environment; `UV_ENV_FILE` put `LD_PRELOAD` into the program of `uv run`). In the new `tests/core/test_subprocess_env_go_yarn.py`, copy the form of `tests/core/test_subprocess_env_gh_kubectl.py`: refused keys `GOFLAGS` and `YARN_YARN_PATH` with the probe in a comment, the refusal test (isolation on and off, each case, the message and `SECURITY_ERROR`), a `run_subprocess` test that starts no child for `GOFLAGS`, and a test that `EXAMPLE_GOFLAGS`, `GOFLAGS_EXAMPLE` and `EXAMPLE_YARN_YARN_PATH` reach the child. the refusal cases of the four keys fail with `DID NOT RAISE`.
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_go_yarn.py tests/core/test_subprocess_env_uv_npm.py` fails on the base
- [x] 1.2 In `src/devops_cli/config/constants.py`, add `"UV_TOOL_DIR"`, `"UV_ENV_FILE"`, `"GOFLAGS"` and `"YARN_YARN_PATH"` to `CONST_CODE_LOADING_ENV_PATTERNS`, in the block of #2673 and after it. Extend the comment of the block with the four probes and with the corrected reason for `UV_ENV_FILE`. In the same comment, say that `npm_config_cache` stays accepted although the probe shows that `npx` starts a program from a prepared cache. The last four files pin the keys that must stay accepted and refused.
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_go_yarn.py tests/core/test_subprocess_env_uv_npm.py tests/core/test_subprocess_env_boundary.py tests/core/test_subprocess_env_file_write.py tests/core/test_subprocess_env_gh_kubectl.py tests/commands/test_install_tools.py` passes

## 2. Keep UV_TOOL_DIR and UV_ENV_FILE out of an isolated child

Reads: `src/devops_cli/core/process.py`, `tests/core/test_subprocess_env_uv_npm.py`. Changes: `src/devops_cli/core/process.py`, `tests/core/test_subprocess_env_uv_npm.py`, `tests/core/test_subprocess_env_go_yarn.py`.

- [x] 2.1 Write the failing tests. In `tests/core/test_subprocess_env_uv_npm.py`, add a test in the form of `test_an_isolated_child_gets_no_uv_project_environment_from_the_environment`: with `UV_TOOL_DIR`, `UV_ENV_FILE`, their lower-case spellings and `UV_CACHE_DIR` in the environment, the isolated child holds `UV_CACHE_DIR` and none of the others, and the child without isolation holds all of them. In `tests/core/test_subprocess_env_go_yarn.py`, add the same test for `GOFLAGS` and `YARN_YARN_PATH`; it passes on the base and pins the behavior. the isolated child still holds `UV_TOOL_DIR` and `UV_ENV_FILE`.
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_uv_npm.py` fails on the base
- [x] 2.2 In `src/devops_cli/core/process.py`, add `"UV_TOOL_DIR"` and `"UV_ENV_FILE"` to `DEFAULT_DENIED_ENV_PATTERNS`, after the entry for UV_PROJECT_ENVIRONMENT, and extend the comment above it: no file of the repository sets either key, so the prefix of `DEFAULT_ALLOWED_ENV_PREFIXES` does not pass them.
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_uv_npm.py tests/core/test_subprocess_env_go_yarn.py tests/core/test_subprocess_env_boundary.py` passes

## 3. Document the refused and accepted keys

Reads: `ARCHITECTURE.md` (the bullets "Uv and npm child environment" and "File-write child environment"), `src/devops_cli/config/constants.py`. Changes: `ARCHITECTURE.md`.

- [x] 3.1 In `ARCHITECTURE.md`, add `UV_TOOL_DIR` and `UV_ENV_FILE` to the bullet "Uv and npm child environment" with the probe results and the corrected reason for `UV_ENV_FILE` (it loads keys, it does not run). Add a bullet "Go and Yarn child environment" for `GOFLAGS` and `YARN_YARN_PATH`: the `-toolexec` result, the Yarn 1 result, the reading of Yarn 4, and the note that no live run of Yarn 4 happened. In the bullet "File-write child environment", add the result of the `npm_config_cache` probe, the reason that it stays accepted, and the duty of a caller that runs `npx` with a cache path from an untrusted source. State that an isolated child gets neither `UV_TOOL_DIR` nor `UV_ENV_FILE` from the environment.
  - Verification: `uv run devops docs check` passes

## Workflow follow-up

- Pending a person: run the live probe of `YARN_YARN_PATH` with Yarn 4 (`npm pack @yarnpkg/cli-dist@4.9.2`, then `node package/bin/yarn.js run <script>` under `env -i`, a temporary `HOME`, a project file and a marker program as the value of the key), and record the result in `ARCHITECTURE.md`. The sandbox of this plan refused to run code that was downloaded from npm.
- Pending a person: confirm that an isolated child must not keep `UV_TOOL_DIR` and `UV_ENV_FILE` from the environment of the person (group 2). The plan drops both, as #2673 does for `UV_PROJECT_ENVIRONMENT`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

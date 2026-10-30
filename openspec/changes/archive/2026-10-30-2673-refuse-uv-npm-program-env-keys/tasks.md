# Tasks

## 1. The guard refuses the uv and npm program keys

- [x] 1.1 Add failing tests: each refused key raises `SecurityError` in each spelling and case with isolation on and off, an isolated child gets no `VIRTUAL_ENV` and no npm program key, the uv settings of the person and the accepted keys reach the child, and `run_subprocess` starts no child
  - Verification: `uv run devops ci test tests/test_subprocess_env_uv_npm.py`
- [x] 1.2 Add the names to `CONST_CODE_LOADING_ENV_PATTERNS` in a block of their own after the gh and kubectl block, and remove `VIRTUAL_ENV` from `DEFAULT_ALLOWED_ENV_VARS`. Change the three lines of `tests/test_subprocess_env_boundary.py` that expect `VIRTUAL_ENV`
  - Verification: `uv run devops ci test tests/test_subprocess_env_uv_npm.py tests/test_subprocess_env_boundary.py tests/test_subprocess_env_gh_kubectl.py tests/test_install_tools.py`

## 2. Documentation

- [x] 2.1 Add a bullet for the uv and npm child environment to `ARCHITECTURE.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [x] 3.1 Archive the change, and name uv and npm in the Purpose of `openspec/specs/subprocess-environment/spec.md`, because the archive command does not edit the Purpose
  - Verification: `uv run devops openspec archive 2673-refuse-uv-npm-program-env-keys`

## Workflow follow-up

- The Go keys (`GOFLAGS` with `-toolexec`): no probe ran, because `go` is not in the devcontainer. A later change probes them with `go` installed.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

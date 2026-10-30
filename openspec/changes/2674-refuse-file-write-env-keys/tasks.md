# Tasks

## 1. The guard refuses the file-write keys

- [x] 1.1 Add failing tests: each refused key raises `SecurityError` in upper and lower case with isolation on and off, an isolated child holds none of them, a child without isolation gets the environment as it is, a key that only contains a refused name reaches the child, and `run_subprocess` starts no child
  - Verification: `uv run devops ci test tests/test_subprocess_env_file_write.py`
- [x] 1.2 Add `SSLKEYLOGFILE`, `QLOGDIR`, `NODE_V8_COVERAGE` and `NODE_REDIRECT_WARNINGS` to `CONST_CODE_LOADING_ENV_PATTERNS` in a block of their own, and replace the four `LD_` names with `LD_*`
  - Verification: `uv run devops ci test tests/test_subprocess_env_file_write.py tests/test_subprocess_env_boundary.py tests/test_subprocess_env_gh_kubectl.py`

## 2. Documentation

- [x] 2.1 Add a bullet for the file-write keys to `ARCHITECTURE.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [ ] 3.1 Archive the change, and name the files that a child writes in the Purpose of `openspec/specs/subprocess-environment/spec.md`, because the archive command does not edit the Purpose
  - Verification: `uv run devops openspec archive 2674-refuse-file-write-env-keys`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

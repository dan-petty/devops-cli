# Tasks

## 1. The guard refuses the gh and kubectl program keys

- [x] 1.1 Add failing tests: each refused key raises `SecurityError` in upper and lower case with isolation on and off, an isolated child holds none of them, the accepted keys reach the child, and `run_subprocess` starts no child
  - Verification: `uv run devops ci test tests/test_subprocess_env_gh_kubectl.py`
- [x] 1.2 Add the seven keys to `CONST_CODE_LOADING_ENV_PATTERNS` in a block of their own, with a comment for each group
  - Verification: `uv run devops ci test tests/test_subprocess_env_gh_kubectl.py tests/test_subprocess_env_boundary.py`

## 2. Documentation

- [x] 2.1 Add a bullet for the gh and kubectl child environment to `ARCHITECTURE.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [x] 3.1 Archive the change, and name gh and kubectl in the Purpose of `openspec/specs/subprocess-environment/spec.md`, because the archive command does not edit the Purpose
  - Verification: `uv run devops openspec archive 2672-refuse-gh-kubectl-code-env-keys`

## Workflow follow-up

- The keys that make a child write a file that the caller names: #2674.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

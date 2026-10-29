# Tasks

## 1. The guard refuses the library and launcher keys

- [x] 1.1 Add failing tests: a caller override of each refused key raises `SecurityError`, in upper and lower case, with isolation on and off
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.2 Add tests: an isolated child holds no refused key from the environment. The keys that load no module reach the child. `run_subprocess` starts no program for a refused key
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.3 Add the block of `OPENSSL*`, `KRB5*`, `GSS_MECH_CONFIG`, `SASL_PATH`, `PYTHONEXECUTABLE` and `__PYVENV_LAUNCHER__` to `CONST_CODE_LOADING_ENV_PATTERNS`, with the pages above them. Keep the comment of the constant at 25 words
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`

## 2. Documentation

- [x] 2.1 Write the child environment bullets of `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec for the library keys
  - Verification: `uv run devops docs check` and `uv run devops openspec check`

## 3. Archive

- [ ] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 2503-refuse-library-code-env-keys`

## Workflow follow-up

- The keys of `ssh` that make an `ssh` child run a program, `SSH_ASKPASS` and `SSH_ASKPASS_REQUIRE`: #2633.
- The keys that make `uv`, `npm` or `go` start a program, for example `UV_PYTHON` and `npm_config_script_shell`: #2673.
- The keys that make a child write a file that the caller names, for example `SSLKEYLOGFILE`: #2674.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

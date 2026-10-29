# Tasks

## 1. The guard refuses the git keys that devops-cli does not set

- [x] 1.1 Add failing tests: a caller override of each refused key raises `SecurityError`, in upper and lower case, with isolation on and off
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.2 Add failing tests: with each refused key in the environment, an isolated child holds none. No key of the allowlist is refused. The five accepted git keys, `XDG_CONFIG_HOME` and `GITHUB_STEP_SUMMARY` reach the child
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.3 Add `GIT_*` and the other keys of the design to `CONST_CODE_LOADING_ENV_PATTERNS`, with the pages above them. Add `CONST_GIT_ACCEPTED_ENV`, and make the guard skip its keys. Keep the comment of the constant at 25 words
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`
- [x] 1.4 Remove `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER` from `DEFAULT_ALLOWED_ENV_VARS`
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_ci.py tests/test_cli_startup_imports.py`

## 2. The own git children pass the guard

- [x] 2.1 Add failing tests: `render_at_revision` through `run_subprocess` starts `ssh` with `-o BatchMode=yes` for an SSH remote. The fetch has `-c core.sshCommand=ssh -o BatchMode=yes`, and each command has only `GIT_TERMINAL_PROMPT=0`
  - Verification: `uv run devops ci test tests/test_k8s_argocd_overrides.py`
- [x] 2.2 Move the SSH option of `CONST_GIT_NONINTERACTIVE_ENV` to `CONST_GIT_NONINTERACTIVE_SSH_CONFIG`, and give it to the `git fetch` of `render_at_revision` as `-c`
  - Verification: `uv run devops ci test tests/test_k8s_argocd_overrides.py tests/test_k8s_deploy_stack_urls.py`
- [x] 2.3 Add a failing test: with `GIT_CONFIG_GLOBAL` in the environment, `devops devcontainer post-start` writes its two git defaults in that file
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [x] 2.4 Add `CONST_GIT_GLOBAL_CONFIG_ENV`, and name it in `extra_allowed_env` of the three `git config --global` calls
  - Verification: `uv run devops ci test tests/test_devcontainer.py tests/test_ssh.py`

## 3. Documentation

- [x] 3.1 Write the child environment bullets of `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec for the git keys
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 2483-refuse-git-code-env-keys`

## Workflow follow-up

- The keys of `ssh` that make an `ssh` child run a program, `SSH_ASKPASS` and `SSH_ASKPASS_REQUIRE`: #2633.
- The library keys that make a library of the child load a module, for example `OPENSSL_CONF`: #2503.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

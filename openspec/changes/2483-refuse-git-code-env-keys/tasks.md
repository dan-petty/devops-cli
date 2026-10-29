# Tasks

## 1. The guard refuses the git keys that make git run a program

- [ ] 1.1 Add failing tests: a caller override of each git key of the design, in upper and lower case, raises `SecurityError` with isolation on and off; with each of them in the environment, the isolated child holds none; `GIT_AUTHOR_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_TERMINAL_PROMPT`, `GIT_CONFIG_NOSYSTEM`, `GIT_SSH_VARIANT`, `GIT_CONFIGURATION` and `EXAMPLE_GIT_SSH_COMMAND` reach the child
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [ ] 1.2 Add the git block to `CONST_CODE_LOADING_ENV_PATTERNS`, with the manual page of each group above its keys, and keep the comment of the constant at 25 words
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`
- [ ] 1.3 Remove `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_EXEC_PATH`, `EDITOR` and `PAGER` from `DEFAULT_ALLOWED_ENV_VARS`
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_ci.py tests/test_cli_startup_imports.py`

## 2. The own git children pass the guard

- [ ] 2.1 Add failing tests: `render_at_revision` through `_run_cmd` fetches an SSH remote with `-o BatchMode=yes` and raises no `SecurityError`; the fetch has `-c core.sshCommand=ssh -o BatchMode=yes` in its arguments; `CONST_GIT_NONINTERACTIVE_ENV` holds only `GIT_TERMINAL_PROMPT=0`
  - Verification: `uv run devops ci test tests/test_k8s_argocd_overrides.py`
- [ ] 2.2 Move the SSH option of `CONST_GIT_NONINTERACTIVE_ENV` to `CONST_GIT_NONINTERACTIVE_SSH_CONFIG`, and give it to the `git fetch` of `render_at_revision` as `-c`
  - Verification: `uv run devops ci test tests/test_k8s_argocd_overrides.py tests/test_k8s_deploy_stack_urls.py`
- [ ] 2.3 Add a failing test: with `GIT_CONFIG_GLOBAL` in the environment, `devops devcontainer post-start` writes the two git defaults in that file and no `.gitconfig` in the home directory
  - Verification: `uv run devops ci test tests/test_devcontainer.py`
- [ ] 2.4 Add `CONST_GIT_GLOBAL_CONFIG_ENV`, and name it in `extra_allowed_env` of the three `git config --global` calls
  - Verification: `uv run devops ci test tests/test_devcontainer.py tests/test_ssh.py`

## 3. Documentation

- [ ] 3.1 Write the child environment bullet of `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec for the git keys, the `-c` option and the `extra_allowed_env` of the `git config --global` calls
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 4. Archive

- [ ] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 2483-refuse-git-code-env-keys`

## Workflow follow-up

- The keys of `ssh` that make an `ssh` child run a program, `SSH_ASKPASS` and `SSH_ASKPASS_REQUIRE`: #2633.
- The library keys that make a library of the child load a module, for example `OPENSSL_CONF`: #2503.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

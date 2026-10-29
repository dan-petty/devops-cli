# Tasks

## 1. The guard refuses the ssh keys and SHELL

- [x] 1.1 Add failing tests for the override of each `SSH_` key and of `SHELL`. Each must raise `SecurityError`, in upper and lower case, with isolation on and off. An isolated child must hold none of these keys from the environment
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.2 Add a test: `DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `TMPDIR`, `LANG`, `HOME`, `SSHPASS` and `EXAMPLE_SSH_ASKPASS` reach the child
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.3 Add a test: with isolation off, the child gets `SHELL` from the environment
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.4 Add `SSH_*` and `SHELL` to `CONST_CODE_LOADING_ENV_PATTERNS`, in a block with a comment line for each. Keep the comment of the constant as it is
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`
- [x] 1.5 Remove `SHELL` from `DEFAULT_ALLOWED_ENV_VARS`
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_ci.py tests/test_cli_startup_imports.py`

## 2. Documentation

- [ ] 2.1 Update the `ARCHITECTURE.md` bullets and the purpose of the `subprocess-environment` spec for the ssh keys and `SHELL`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [ ] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 2633-refuse-ssh-code-env-keys`

## Workflow follow-up

- The library keys that make a library of the child load a module, for example `OPENSSL_CONF`: #2503.
- The keys of `gh` and `kubectl` that name a program, for example `GH_EDITOR`, `GH_BROWSER`, `KUBE_EDITOR` and `KUBECTL_EXTERNAL_DIFF`: #2672.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

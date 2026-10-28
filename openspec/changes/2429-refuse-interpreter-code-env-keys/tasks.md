# Tasks

## 1. The guard refuses the zsh and interpreter keys that load or run code

- [x] 1.1 Add failing tests: a caller override of each zsh, Python, Node.js, Perl, Ruby and Java key of the design, in upper and lower case, raises `SecurityError` with isolation on and off; `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE` and `NODE_ENV` reach the child
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 1.2 Add the keys to `CONST_CODE_LOADING_ENV_PATTERNS`, with the manual page of each family in a comment
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_review_rules_pack.py`

## 2. An isolated child gets no refused key from the environment

- [x] 2.1 Add a failing test: with each refused key in the environment, the isolated child environment holds none of them
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py`
- [x] 2.2 Remove `PYTHONPATH` and `PYTHONHOME` from `DEFAULT_ALLOWED_ENV_VARS`
  - Verification: `uv run devops ci test tests/test_subprocess_env_boundary.py tests/test_ci.py tests/test_cli_startup_imports.py`
- [x] 2.3 Write the child environment bullet of `ARCHITECTURE.md` and the purpose of the `subprocess-environment` spec for the zsh and interpreter keys, and name the git keys (#2483)
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- The git keys that make a git child run a program, for example `GIT_CONFIG_*` and `GIT_SSH_COMMAND`: #2483.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

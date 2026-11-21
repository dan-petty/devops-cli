# Tasks

## 1. The git configuration keys of the environment (behavior)

- [x] 1.1 Write the failing tests: a git child of a person gets the keys and no `-c` value, no child of the GitHub App gets them with isolation on or off, and `worktrees add` reads a private `origin` with the helper of the environment.
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/git/test_repos_worktrees_reclaim.py`
- [x] 1.2 Give the keys to each child of a person in `build_subprocess_env`, and to no child of the GitHub App. Delete `git_credential_args`, its two inserts and `_command_words`.
  - Verification: `$ uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/core/test_process.py tests/git/test_repos_worktrees_reclaim.py`

## 2. The per-call credential values (refactor)

- [x] 2.1 Delete the credential `-c` values of `devops infra` (`repo_tree.py`) and of `render_at_revision`, and update their tests and the dry-run snapshots.
  - Verification: `$ uv run devops ci test tests/infra tests/k8s/test_k8s_argocd_overrides.py tests/commands/test_infra_apply.py tests/commands/test_infra_onboard.py tests/commands/test_infra_plan.py tests/commands/test_infra_status.py`
- [x] 2.2 Check that no code in `src/` inserts credential `-c` values into a git argument list.
  - Verification: `$ ! git grep -n -E "git_credential_args|_command_words\(argv|for value in CONST_GIT_GITHUB_CREDENTIAL_CONFIG" src/`

## 3. Documents

- [x] 3.1 Describe the keys in `SECURITY.md`, `ARCHITECTURE.md` and `docs/DEVCONTAINER_USAGE.md`, and change the specs `subprocess-environment`, `gitops-host-overrides` and `repos-worktrees-add`.
  - Verification: `$ uv run devops ci --check --only docs,openspec`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

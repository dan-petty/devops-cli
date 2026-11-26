# Tasks

## 1. Behavior: the add command installs no Node tools

- [x] 1.1 Write a failing test: `devops repos worktrees add` records no `npm` call for a repository that holds `package-lock.json`, and the worktree exists
  - Verification: `$ uv run devops ci test tests/core/test_repos_worktrees_add.py`
- [x] 1.2 Delete `install_node_tools`, its call in `worktrees_add`, its imports and the message `worktrees_add_node_tools_failed`
  - Verification: `$ uv run devops ci test tests/core/test_repos_worktrees_add.py`

## 2. Documents

- [x] 2.1 Say in CONTRIBUTING.md and docs/DEVCONTAINER_USAGE.md where a worktree gets `openspec` from and how to find a stale copy on `PATH`, restore the worktree step of docs/DESIGN.md, and regenerate docs/commands/repos.md
  - Verification: `$ uv run devops ci docs`

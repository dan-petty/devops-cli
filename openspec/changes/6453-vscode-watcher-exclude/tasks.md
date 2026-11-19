# Tasks

## 1. Exclude the large folders from the file watcher

Kind: other. Changes: `.vscode/settings.json`.

- [ ] 1.1 Add `files.watcherExclude` with `.data/**`, `repos/**`, `.claude/worktrees/**`, `.venv/**`, `.mypy_cache/**`, `.ruff_cache/**`, `.pytest_cache/**` and `mutants/**`
  - Verification: `$ uv run devops ci --check --only lint,format`

## 2. Documents

Kind: documents. Changes: `docs/DEVCONTAINER_USAGE.md`.

- [ ] 2.1 Tell in "The Devcontainer of This Repository" where the setting is, why, and how to count the watches
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: reload the VS Code window of the workspace after the merge, then count the watches of the process with `--type=fileWatcher`. The count must be less than 10 percent of `/proc/sys/fs/inotify/max_user_watches`.

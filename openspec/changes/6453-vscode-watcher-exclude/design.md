# Design

## Decisions
- **The setting is in `.vscode/settings.json`.** VS Code and Antigravity both read the workspace settings, so one entry covers both editors. VS Code starts its watcher again when `files.watcherExclude` changes, so the setting applies with no rebuild of the container. The paths are paths of this workspace, so the workspace scope is correct.
- **The patterns start at the workspace folder.** The default patterns of VS Code do not start with `**`, because a `**` pattern makes a slow regular expression in a large workspace. A census found `.venv`, `.mypy_cache`, `.ruff_cache` and `.pytest_cache` only at the root, outside the excluded trees.
- **The setting does not repeat the default excludes.** VS Code merges an object setting with its default (`mergeContents` in `configurationModels.ts`). A copy of the defaults would also stop new defaults of VS Code.
- **`.claude/worktrees/**` is excluded.** Claude Code makes its worktrees there, and they held 93127 folders, which is 18 percent of the limit.

## Rejected alternatives
- **`customizations.vscode.settings` of `.devcontainer/devcontainer.json`**: these values go to the machine settings of the container when the container is created, so a change applies only after a rebuild. The file also needs a second copy under `customizations.antigravity`. The home volume is shared, so a machine setting also applies to the other repositories that use the volume.
- **A larger `max_user_watches`**: the limit is a setting of the host kernel. A larger limit gives more memory to watches that VS Code does not need.
- **`files.exclude` or `search.exclude`**: `workspaceWatcher.ts` does not read them, so they do not change the watcher.
- **Move the agent worktrees out of the workspace**: this needs a decision of a person, and the setting stops the watches with no move.

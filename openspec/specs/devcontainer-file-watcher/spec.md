# devcontainer-file-watcher Specification

## Purpose
The file watcher of the editor in the workspace container: VS Code must not use the inotify watches of the user for agent worktrees, clones and caches, so that other programs can add a watch.

## Requirements

### Requirement: The editor does not watch agent worktrees and clones
`.vscode/settings.json` SHALL set `files.watcherExclude` for `.data/**`, `repos/**`, `.claude/worktrees/**`, `.venv/**`, `.mypy_cache/**`, `.ruff_cache/**`, `.pytest_cache/**` and `mutants/**`. The setting SHALL NOT repeat the default excludes of VS Code, because VS Code merges an object setting with its default.

#### Scenario: The file watcher holds a small part of the watches
- **WHEN** a person reloads the VS Code window of the workspace and counts the `inotify` lines of `/proc/<pid>/fdinfo/*` for the process with `--type=fileWatcher`
- **THEN** the count is less than 10 percent of `/proc/sys/fs/inotify/max_user_watches`

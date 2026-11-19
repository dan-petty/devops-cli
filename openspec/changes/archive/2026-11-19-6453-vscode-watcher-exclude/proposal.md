# Proposal: #6453

## Why
The VS Code file watcher of the workspace container uses almost all inotify watches of the user (#6453). Then other programs cannot add a watch. For example, aardvark-dns stops when it cannot watch `/etc/resolv.conf`, and file watchers of tests and tools fail. The watcher watches each folder of the agent worktrees under `.data/`, the clones under `repos/` and the worktrees of Claude Code under `.claude/worktrees/`, because no setting excludes them.

## What Changes
- `.vscode/settings.json` sets `files.watcherExclude` for `.data/**`, `repos/**`, `.claude/worktrees/**`, `.venv/**` and the tool caches `.mypy_cache/**`, `.ruff_cache/**`, `.pytest_cache/**` and `mutants/**`.
- `docs/DEVCONTAINER_USAGE.md` tells where the setting is and how to count the watches.
- The change has a spec delta: the folders that the editor watches are behavior that a developer sees. The proof is a live count, because no test reads a config value.
- The change fits one pull request.

## Capabilities
- New: `devcontainer-file-watcher`.

## Impact
- VS Code and Antigravity read the workspace settings, so the one setting applies to both editors.
- VS Code does not send change events for files in the excluded folders. An editor tab that shows such a file does not update when an agent changes the file.
- No code under `src/` changes.

## Feasibility
- On 2026-11-19 the process with `--type=fileWatcher` of VS Code Insiders 1.148.0 held 524137 watches. The limit `/proc/sys/fs/inotify/max_user_watches` is 524288. The count is the `inotify` lines of `/proc/<pid>/fdinfo/*`.
- `find -type d` counted the folders of the checkout: `.data` 381348, `.claude/worktrees` 93127, `repos` 37797 and `.venv` 8056. With the new excludes and the default excludes, 8033 folders stay.
- The VS Code source (`src/vs/platform/files/node/watcher/parcel/parcelWatcher.ts`) gives `files.watcherExclude` to `@parcel/watcher` as `ignore`, so the watcher adds no watch for an excluded folder.
- `workspaceWatcher.ts` reads only `files.watcherExclude`, so `files.exclude` and `search.exclude` do not change the watcher.
- `configurationModels.ts` merges an object setting with its default, so the workspace value adds to the default excludes of VS Code and does not replace them.

## Existing Tool Considered
- The `files.watcherExclude` setting of VS Code covers the need. The change builds no code and deletes no internal code.

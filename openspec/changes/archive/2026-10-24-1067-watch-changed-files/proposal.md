# Proposal

## Why

Issue #1067: `devops review path --watch` reviews every target again whenever any watched file changes.
When a person saves one file in a watched directory, the command runs a full review of all files under the targets.
With the reply cache on, pre-analysis, static analysis, and verification still process all files and write a new session for all files.
With cache disabled or forced, every page calls the model again.

## What Changes

- On a change, `devops review path --watch` reviews only the changed files that still exist, lie under one of the targets, and pass `--pattern` and reviewable-file filters.
- A deleted file is skipped. A change with no reviewable file prints one line and runs no review.
- The command applies the same stage flags, personas, concurrency, and clients to the changed files.
- `HELP.options.watch` states that each change reviews only the changed files.
- A unit test verifies that `review path --watch` passes only changed files to the review workflow and runs no review when only a deleted file changes.

## Capabilities

### New Capabilities

- `review-path-watch`: path review watch mode filters change events to review only existing reviewable files under target paths.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/review.py`, `src/devops_cli/ai/review/runner.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_review.py`.
- Documentation: `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md`, `docs/commands/ai.md`, `docs/commands/review.md`, regenerated via `devops docs generate --sync-readme`.

## Feasibility

- `DebouncedFileWatcher` in `src/devops_cli/watchers/file_watcher.py` already delivers the modified `list[Path]` to `on_change`.
- In `src/devops_cli/commands/review.py`, `_on_change(changed)` ignored `changed` and called `_execute_current_review()`, which reviewed all targets.
- Target boundaries, relative paths, pattern matching, git-ignore rules, and `is_secret_scan_only` exist in `src/devops_cli/ai/review/runner.py` and `src/devops_cli/review/targets.py`.
- Passing changed files through review filtering satisfies the acceptance criteria without external dependencies or breaking changes.

## Existing Tool Considered

`DebouncedFileWatcher` is the repository's file watching abstraction based on `os.walk` and file modification timestamps. No new file watching tool is needed.

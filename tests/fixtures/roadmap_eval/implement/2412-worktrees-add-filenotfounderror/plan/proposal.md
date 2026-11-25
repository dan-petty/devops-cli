# Proposal

## Why

Issue #2412: `devops repos worktrees add` stops with an unhandled `FileNotFoundError`. The error occurs when another process deletes a file while the reclaim step measures that worktree. `directory_size` in `src/devops_cli/git/worktree_inventory.py` walks the directory with `os.walk` and calls `os.lstat` on each listed file name. A file that is deleted between the `os.walk` listing and the `os.lstat` call makes `os.lstat` raise `FileNotFoundError`. The reclaim step measures the worktrees of merged work, which another agent or command can remove at the same time.

## What Changes

- `directory_size` catches `FileNotFoundError` when it measures the size of a file.
- A file that is gone when `os.lstat` runs contributes 0 bytes to the total.
- `devops repos worktrees add` completes and creates the new worktree when files in a measured worktree are deleted concurrently.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-worktrees-prune`: when a file is deleted while `directory_size` measures a worktree, the measurement does not raise an error.

## Impact

- `src/devops_cli/git/worktree_inventory.py`: `directory_size` handles `FileNotFoundError` for missing files during the directory walk.
- Tests: `tests/test_repos_worktrees.py` adds tests that verify `directory_size` returns the correct size without error when files are deleted during measurement.

## Feasibility

- Confirmed against the source at `origin/main` (d739a472): `directory_size` calls `os.lstat(os.path.join(top, name)).st_size` in a comprehension. No exception handler wraps the `os.lstat` call.
- Confirmed with reproduction: when `os.lstat` raises `FileNotFoundError` on a file listed by `os.walk`, `directory_size` fails immediately with an unhandled exception.
- Catching `FileNotFoundError` around `os.lstat` and returning 0 bytes allows `directory_size` to complete safely.

## Existing Tool Considered

Python standard library `os.walk` does not suppress errors on `os.lstat` calls made by caller code. The application must catch `FileNotFoundError` on the `os.lstat` invocation directly. No other tool is needed for this fix.

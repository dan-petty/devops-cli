# Design

## Context

See proposal.md for the background. `directory_size` in `src/devops_cli/git/worktree_inventory.py` computes the size in bytes of a directory tree. It traverses files using `os.walk` and computes the size of each file with `os.lstat`.

## Goals / Non-Goals

**Goals:**
- Make `directory_size` resilient against concurrent file deletions.
- Return the sum of bytes for all files that remain accessible.
- Avoid raising `FileNotFoundError` during `devops repos worktrees add` reclaim steps.

**Non-Goals:**
- Change the directory traversal mechanism from `os.walk`.
- Catch unrelated errors such as permission errors.
- Retry deleted files.

## Decisions

### 1. Catch `FileNotFoundError` in a helper function
- Decision: Introduce a helper function `_file_size(path: str) -> int` that wraps `os.lstat(path).st_size` in a `try...except FileNotFoundError` block, returning 0 on error.
- Rationale: A helper function keeps `directory_size` readable and concise. Catching only `FileNotFoundError` specifically addresses the race condition without masking unexpected filesystem errors.
- Alternative considered: Use an inline helper or catch broader `OSError`.
  - Rejected: Catching `OSError` could mask permission or hardware failures. An inline generator with try-except requires more complex syntax than a clear single-responsibility helper.

### 2. Missing files contribute zero bytes
- Decision: When a file is missing at `os.lstat` time, return 0 bytes.
- Rationale: The file is already deleted, so it consumes no space in the directory.

## Risks / Trade-offs

- [A file deleted mid-walk may produce a slightly lower total size than before deletion started] -> This is expected and accurate because the file no longer exists.

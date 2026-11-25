### Problem Description

`devops repos worktrees add` stops with an unhandled `FileNotFoundError` traceback when a file in another worktree is deleted while the reclaim step measures that worktree. `directory_size` (`src/devops_cli/git/worktree_inventory.py:324`) walks the directory with `os.walk` and calls `os.lstat` on each name. A file that `os.walk` listed and that another process then deletes makes `os.lstat` raise, and the error ends the whole command. The reclaim step measures the worktrees of merged work (`_size_of`, called at lines 438 and 492), and these are the worktrees that another agent's `worktrees add` or `worktrees prune --confirm` removes at the same time.

### Reproduction Steps

1. Have a worktree of merged work under `.data/agent/worktrees/`, with a `.venv`.
2. Start `uv run devops repos worktrees add <issue> --type feat --slug <slug>` in two sessions at about the same time, or start one while `uv run devops repos worktrees prune --confirm` removes that worktree.
3. One run walks the worktree while the other deletes its files.

Seen on 2026-10-28 while several agents started worktrees at once.

### Expected vs Actual Behavior

Expected: a file that is gone when it is measured counts as 0 bytes (or the directory's size is reported as unknown), and the command goes on to create the worktree.

Actual: the command ends with a traceback, and the worktree is not created. A retry with `--no-reclaim` works.

### Environment Diagnostics

devops-cli at origin/main bb46660c, Python 3.14, Linux devcontainer (rootless Podman on WSL2).

### Logs, Traces, or Terminal Output

```
│   324 def directory_size(path: Path) -> int:
│   325 │   """The bytes of every file under `path`, links counted as links and not followed."""
│   326 │   return sum(
│ ❱ 327 │   │   os.lstat(os.path.join(top, name)).st_size
│   328 │   │   for top, _dirs, names in os.walk(path)
│   329 │   │   for name in names
│   330 │   )
FileNotFoundError: [Errno 2] No such file or directory:
'<repo>/.data/agent/worktrees/w-<n>/.venv/lib/python3.14/site-packages/authlib/integrations/base_client/async_app.py'
```

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=73d180770396c73d6a4c990bbbe035d084b5f76d -->
## Proposed design

### Problem statement
The `directory_size` function in `src/devops_cli/git/worktree_inventory.py` walks a directory with `os.walk` and calls `os.lstat` on each listed name. When another process deletes a file between the `os.walk` listing and the `os.lstat` call, the function raises an unhandled `FileNotFoundError`. This crashes the `devops repos worktrees add` command during its reclaim step, which measures worktrees of merged work. The crash prevents worktree creation and has no retry path other than `--no-reclaim`.

### Acceptance criteria
- Criterion 1: `directory_size` returns a byte count without raising when a file is deleted during the walk.
  Verification: Run `uv run devops ci test tests/test_repos_worktrees.py` with a test that creates a file, starts a thread that deletes it, and calls `directory_size`. The call returns an int and does not raise `FileNotFoundError`.
- Criterion 2: A file that is gone when `os.lstat` runs contributes 0 bytes to the total.
  Verification: The test asserts the returned size equals the sum of the files that still exist, excluding the deleted file.
- Criterion 3: `devops repos worktrees add` completes and creates the worktree when a concurrent process deletes files in a measured worktree.
  Verification: A test or integration scenario runs `worktrees add` while another process removes files in a merged worktree. The command exits 0 and the new worktree exists.
- Criterion 4: The existing tests for `directory_size` and `_size_of` still pass.
  Verification: Run `uv run devops ci test tests/test_repos_worktrees.py` and confirm all tests pass.

### Key questions
- **Which exception should `directory_size` catch around `os.lstat`?**: Catch `FileNotFoundError`. It is the exception raised when a file listed by `os.walk` is deleted before `os.lstat` runs. Catching the broader `OSError` is not needed for this race. (proposed) [sources: src/devops_cli/git/worktree_inventory.py:324]
- **What value should a missing file contribute to the size total?**: Zero bytes. The file is gone, so it adds nothing to the directory size. The command continues with the partial total. (proposed)
- **Is the change confined to `directory_size` in `worktree_inventory.py`?**: Yes. The function at line 324 is the only place that calls `os.lstat` in the walk. `_size_of` at line 333 already handles the case where the directory itself is gone by returning `None`. No other call site needs a change. [sources: src/devops_cli/git/worktree_inventory.py:324, src/devops_cli/git/worktree_inventory.py:333]

### Open questions
- Is #2408 a dependency of this issue? (missing verified source)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

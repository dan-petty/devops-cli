### Problem Description

A `devops gh api` call printed a `FileNotFoundError` traceback when its working directory no longer existed. The post-merge worktree cleanup had deleted the directory. The telemetry setup calls `_resolve_git_dir` (`src/devops_cli/telemetry/tracer.py`), which starts from `Path.cwd()`, and `Path.cwd()` raises `FileNotFoundError` for a deleted directory. The command did not report a clean error.

### Reproduction Steps

1. `mkdir /tmp/gone && cd /tmp/gone && rmdir /tmp/gone`
2. `uv run --project /workspaces/devops-cli devops gh api rate_limit`

### Expected vs Actual Behavior

Expected: telemetry finds no git directory and the command runs, or the command stops with one error line that says the working directory does not exist.

Actual: a `FileNotFoundError` traceback from `_resolve_git_dir`.

### Environment Diagnostics

`main` at 2026-10-28, devcontainer.

### Logs, Traces, or Terminal Output

```
telemetry/tracer.py in _resolve_git_dir -> Path.cwd()
FileNotFoundError: [Errno 2] No such file or directory
```

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=0f7bc266fd52ad4b6ad23bf65b710cd20c398b18 -->
## Proposed design

### Problem statement
A devops command run from a deleted working directory crashes with an unhandled FileNotFoundError traceback. The telemetry setup calls _resolve_git_dir, which calls Path.cwd(). Path.cwd() raises FileNotFoundError when the directory no longer exists. The command does not report a clean error and does not complete.

### Acceptance criteria

### Requirement: Deleted CWD returns no git directory
_resolve_git_dir SHALL return None when Path.cwd() raises FileNotFoundError because the working directory no longer exists.

#### Scenario: CWD deleted before call
- **WHEN** Path.cwd() raises FileNotFoundError because the process working directory was removed
- **THEN** _resolve_git_dir returns None and no exception propagates to the caller

### Requirement: Command completes without traceback
A devops command run from a deleted working directory SHALL complete without an unhandled FileNotFoundError traceback from the telemetry setup.

#### Scenario: gh api from deleted directory
- **WHEN** a devops gh api command runs after its working directory has been deleted
- **THEN** the command exits with a clean result or a single error line, not a traceback

### Requirement: Normal resolution unaffected
_resolve_git_dir SHALL return the correct git directory when the working directory exists and contains a .git entry.

#### Scenario: CWD inside a git repository
- **WHEN** the process working directory exists and is inside a git repository
- **THEN** _resolve_git_dir returns the path to the .git directory as before

### Existing Tool Considered
No external tool or library covers this need. The fix is a try/except OSError around the Path.cwd() call in _resolve_git_dir (src/devops_cli/telemetry/tracer.py:628). The written cost is one try/except block of about 4 lines, one test case, and the maintenance of that guard for the lifetime of the function.

### Key questions
- **Where in the call chain should the FileNotFoundError from Path.cwd() be caught?**: In _resolve_git_dir itself, at the Path.cwd() call site. This is the origin of the exception, and the function already returns None when no git directory is found, so returning None on a deleted CWD is consistent with its contract. Catching it in _detect_vcs_metadata would leave _resolve_git_dir vulnerable for any other caller. (best practice) [sources: src/devops_cli/telemetry/tracer.py:628, src/devops_cli/telemetry/tracer.py:646]
  - Chosen: Catch in _resolve_git_dir at the Path.cwd() call. Most targeted fix. Protects all callers. Matches the function's existing None-return contract for the not-found case.
  - Rejected: Catch in _detect_vcs_metadata. Leaves _resolve_git_dir vulnerable for other callers. The exception would still propagate if any other code calls _resolve_git_dir directly.
  - Rejected: Catch in the CLI entry point. Too broad. Hides the specific cause and makes the telemetry path less testable in isolation.
- **Which exception type should the handler catch?**: OSError. FileNotFoundError is a subclass of OSError. Path.cwd() can raise OSError for reasons other than a missing directory (for example, a permission error on the underlying getcwd syscall). The existing code in this file already catches OSError in _resolve_git_dir_from_file and _read_packed_refs, so OSError is the established pattern. (best practice) [sources: src/devops_cli/telemetry/tracer.py:618, src/devops_cli/telemetry/tracer.py:596]
  - Chosen: Catch OSError. Covers FileNotFoundError and any other OS-level failure from getcwd. Matches the existing pattern in this file.
  - Rejected: Catch FileNotFoundError only. Narrower than needed. A permission error on getcwd would still crash the command.
- **What value should _resolve_git_dir return when the CWD is unavailable?**: None. The function's signature is Path | None, and it already returns None when no .git entry is found in the directory tree. A deleted CWD is another case of 'no git directory found', so None is the correct and consistent return. (best practice) [sources: src/devops_cli/telemetry/tracer.py:628]
  - Chosen: Return None. Matches the existing not-found contract. The caller _detect_vcs_metadata already handles None by returning an empty dict.
  - Rejected: Raise a custom exception. Adds a new exception type for a case that is semantically identical to 'no git directory found'. Unnecessary complexity.
- **Does _normalize_code_filepath need the same guard?**: No. It already wraps its body in try/except Exception and returns the original filepath on any failure. A FileNotFoundError from Path.cwd() inside that function is already caught. [sources: src/devops_cli/telemetry/tracer.py:700]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

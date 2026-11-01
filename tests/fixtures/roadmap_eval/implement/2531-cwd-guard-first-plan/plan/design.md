# Design

## Decisions

- **Catch OSError in _resolve_git_dir at the Path.cwd() call site**: This is the origin of the exception. The function already returns None when no git directory is found, so returning None on a deleted CWD is consistent with its contract. Catching it here protects all callers, not just _detect_vcs_metadata.
- **Catch OSError rather than FileNotFoundError**: FileNotFoundError is a subclass of OSError. Path.cwd() can raise OSError for reasons other than a missing directory, such as a permission error on the getcwd syscall. The existing code in this file already catches OSError in _resolve_git_dir_from_file and _read_packed_refs, so OSError is the established pattern.
- **Return None when the CWD is unavailable**: The function signature is Path | None, and it already returns None when no .git entry is found. A deleted CWD is another case of no git directory found. The caller _detect_vcs_metadata already handles None by returning an empty dict.

## Rejected alternatives

- **Catch the exception in _detect_vcs_metadata**: This leaves _resolve_git_dir vulnerable for any other caller. The exception would still propagate if any other code calls _resolve_git_dir directly. The fix at the origin is more targeted.
- **Catch the exception in the CLI entry point**: Too broad. It hides the specific cause and makes the telemetry path less testable in isolation. A targeted guard at the call site is simpler and more precise.
- **Catch FileNotFoundError only**: Narrower than needed. A permission error on getcwd would still crash the command. OSError covers all OS-level failures from the getcwd syscall.
- **Raise a custom exception for a deleted CWD**: Adds a new exception type for a case that is semantically identical to no git directory found. The existing None-return contract already covers this. Unnecessary complexity.

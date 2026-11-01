# Design

## Decisions

- **Return `None` from `_resolve_git_dir` when `Path.cwd()` raises `OSError`.** The function returns `Path | None` and already returns `None` when it finds no `.git` entry. A removed directory is one more case of "no git directory". `_detect_vcs_metadata` already treats `None` as "no attributes". `OSError` is the established pattern in the same file (`_resolve_git_dir_from_file`, `_read_packed_refs`, `_read_ref_file`), and it covers `FileNotFoundError`.
- **Stop a command at the exit seam when `os.getcwd()` raises `FileNotFoundError`.** `OTelTyper.command` wraps every command. The wrapper raises a `DevOpsCLIError` with the message "The working directory does not exist.", and `_report_devops_error` prints it as one line with exit status 1. This is the "one error line" case of the issue. Only `FileNotFoundError` is the case of the issue; another `OSError` of `os.getcwd()` is out of scope and propagates as before.
- **Check in the command wrapper, not in `_report_devops_error`.** `_report_devops_error` also wraps group callbacks, and `devops gh --help` runs the callback of its group. A check there made `devops gh --help` fail in a scratch copy, where it works on `origin/main`.
- **Keep both guards.** The seam covers every command. The guard in `_resolve_git_dir` covers a caller that starts a span outside a command, and meets the first requirement of the issue.

## Rejected alternatives

- **Guard `_resolve_git_dir` only.** The command then fails at `settings.py:1313` (`_config_layers`, `os.getcwd()`). The scratch run is in the proposal.
- **Guard each `Path.cwd()` and `os.getcwd()` call.** There are 47 calls in `src/` (`git grep -nE "os\.getcwd\(\)|Path\.cwd\(\)" -- src | wc -l`). Each needs its own fallback, and the next new call breaks the rule again.
- **Catch the error in `_detect_vcs_metadata`.** `_resolve_git_dir` would still raise for any other caller.
- **Change to a fallback directory such as the home directory.** Relative paths of the command would then point to a place the person did not choose, and the command would run with a wrong root.
- **A custom exception class for a removed directory.** The message and the status are all the person needs, and `DevOpsCLIError` is raised directly in other places (`src/devops_cli/ai/inspection.py`).

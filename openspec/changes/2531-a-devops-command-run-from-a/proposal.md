# Proposal

## Why

Issue #2531: a devops command that runs from a working directory that no longer exists prints a `FileNotFoundError` traceback. A worktree cleanup after a merge can remove the directory of a running shell. The first crash is in `_resolve_git_dir` (`src/devops_cli/telemetry/tracer.py`), which calls `Path.cwd()`. The issue asks that the command run, or stop with one error line, and that `_resolve_git_dir` return `None` for a deleted directory.

A guard in `_resolve_git_dir` alone does not give that. The next crash is in `_config_layers` (`src/devops_cli/config/settings.py`), which calls `os.getcwd()`. The source holds 47 more calls of `Path.cwd()` or `os.getcwd()`. This change guards `_resolve_git_dir`, and it stops a command at the exit seam of `new_typer()` with one error line.

## What Changes

- `_resolve_git_dir` returns `None` when `Path.cwd()` raises `OSError`. A span then starts with no `vcs.*` attribute.
- A command of a `new_typer()` app checks the working directory before it runs. When the directory is gone, the command prints one error line, exits with status 1 and runs no body. A group that shows its help is not a command and keeps working.
- The paragraph of `ARCHITECTURE.md` on the exit seam names this check.
- The change fits one pull request. It has two task groups.

This change alters what a person observes (a command message and a span), so it carries spec deltas: `command-telemetry` and `command-error-exit`.

## Capabilities

### Modified Capabilities

- `command-telemetry`: a span starts without VCS attributes when the working directory is gone, and keeps them when it exists.
- `command-error-exit`: a command run from a deleted working directory stops with one error line.

## Acceptance

Acceptance criteria of #2531, from the refine block of the issue:

- Deleted CWD returns no git directory: group 1 (a span starts with no `vcs.*` attribute, which needs `_resolve_git_dir` to return `None`).
- Command completes without traceback: group 2 (one error line, status 1, no traceback).
- Normal resolution unaffected: group 1 (a test pins the `vcs.*` attributes of a client inside a git repository).

## Impact

- Code: `src/devops_cli/telemetry/tracer.py` (`_resolve_git_dir`), `src/devops_cli/core/cli.py` (`OTelTyper.command`).
- Tests: `tests/telemetry/test_telemetry.py`, `tests/commands/test_command_error_exit.py`.
- Documents: `ARCHITECTURE.md` (section 7, the exit seam).
- Existing code the change keeps: `_detect_vcs_metadata` already treats `None` as "no git directory" and returns an empty mapping. `reset_tracer()` clears its cache, which the tests use. `_report_devops_error` prints a `DevOpsCLIError` as one line and exits with its status. The test `test_every_command_app_passes_its_commands_through_the_exit_seam` and the requirements of `command-error-exit` must still pass.

## Feasibility

Every check below ran on `origin/main` (0.37.1) on 2026-11-01, in a worktree of this branch.

- The crash exists. `mkdir /tmp/gone && cd /tmp/gone && rmdir /tmp/gone`, then `.venv/bin/devops gh api rate_limit` ends with `tracer.py:646 in _detect_vcs_metadata`, `tracer.py:630 in _resolve_git_dir`, `pathlib/__init__.py:927 in cwd` and `FileNotFoundError: [Errno 2] No such file or directory`. The line of the issue (628) is now 630.
- The mechanism is as the issue says. `git grep -n "Path.cwd" -- src/devops_cli/telemetry/tracer.py` shows `current = (start_dir or Path.cwd()).resolve()` in `_resolve_git_dir`, with no handler. `_detect_vcs_metadata` runs `if git_dir is not None:`, so `None` gives an empty mapping.
- The guard alone is not enough. A scratch run of the same command with `_resolve_git_dir` wrapped to return `None` on `OSError` still fails: `settings.py:1396 in load_settings`, `settings.py:1313 in _config_layers`, `os.getcwd()`, reached from `run_gh` and `get_github_rate_limiter`. `git grep -nE "os\.getcwd\(\)|Path\.cwd\(\)" -- src | wc -l` prints 47. So a guard at each site is not a bounded change.
- The seam works. With a check of `os.getcwd()` added to `OTelTyper.command` in a scratch copy, `devops gh api rate_limit`, `devops config show` and `devops pr list` from a deleted directory each print `The working directory does not exist.` with exit status 1 and no traceback. `devops --version` and `devops gh --help` still work. A copy that put the check in `_report_devops_error` also broke `devops gh --help`, because the group callback uses that seam. So the check belongs to the command wrapper only.
- The public interface shows the first defect. A scratch script that removes its working directory, calls `reset_tracer()` and starts `OTelTelemetryClient(enabled=True).span("x")` raises `FileNotFoundError` from `Path.cwd()` on `origin/main`. A test through this interface needs no patch of a devops-cli name, as `docs/TESTING.md` requires.
- `_normalize_code_filepath` needs no guard, as the issue says: `git grep -n -A8 "def _normalize_code_filepath" -- src/devops_cli/telemetry/tracer.py` shows its body in `try: ... except Exception: return filepath`.
- Nothing newer did this. `git log origin/main --oneline -i --grep="working directory"` and `--grep="getcwd"` list only #2128 and #2619 (reviews take the workspace from the caller) and the plan #2995. The last change to the exit seam in `src/devops_cli/core/cli.py` is #2502 (eadd55f1). This change extends that seam. The newer commit #2708 is a dashboard change and does not touch the seam. The search of issues for "deleted working directory" finds only #2531 and its plan.
- The test file of the first plan, `tests/test_tracer.py`, does not exist on `origin/main`. The tracer tests sit in `tests/telemetry/test_telemetry.py`. The seam tests sit in `tests/commands/test_command_error_exit.py`.

## Existing Tool Considered

The standard library covers the need: `os.getcwd()` raises `FileNotFoundError` for a removed directory, and the change catches it. No external tool or library does more. The written cost is two short guards (about 10 lines), three tests, one paragraph of `ARCHITECTURE.md`, and the upkeep of the check in `OTelTyper.command`. The change deletes no internal code.

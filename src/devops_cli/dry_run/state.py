"""Dry-run execution state and rendering helpers."""

from __future__ import annotations

import os
import shlex
from typing import Any

_DRY_RUN_ENV = "DEVOPS_CLI_DRY_RUN"

# Whether this process turned dry-run on, as opposed to inheriting it. The variable alone
# cannot answer that, and the difference decides whether a command without `--dry-run`
# should clear it: a request the caller exported outlives one invocation, a `--dry-run`
# flag does not.
_ACTIVATED_HERE = False


def set_dry_run(enabled: bool) -> None:
    """Set global dry-run mode in environment."""
    global _ACTIVATED_HERE
    _ACTIVATED_HERE = enabled
    if enabled:
        os.environ[_DRY_RUN_ENV] = "true"
        return
    os.environ.pop(_DRY_RUN_ENV, None)


def dry_run_requested_by_environment() -> bool:
    """Report whether the caller's environment asked for dry-run.

    A `--dry-run` flag applies to the invocation that carried it, so a later command in the
    same process must not inherit it. An exported `DEVOPS_CLI_DRY_RUN` applies to every
    command in that environment, so a later command must not discard it.
    """
    return is_dry_run() and not _ACTIVATED_HERE


def is_dry_run() -> bool:
    """Check if dry-run mode is enabled."""
    value = os.environ.get(_DRY_RUN_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_dry_run_requested(args: list[str]) -> bool:
    """Return True if --dry-run flag is present in argument list."""
    return "--dry-run" in args


def format_command(command: list[str], *, cwd: str | None = None) -> str:
    """Format shell command string for dry-run output."""
    rendered = shlex.join(command)
    if cwd:
        return f"(cd {shlex.quote(cwd)} && {rendered})"
    return rendered


def render_dry_run_result(
    command: str,
    action: str = "",
    target: str | None = None,
    details: dict[str, Any] | None = None,
) -> Any:
    """Construct and print structured CommandDryRunResult JSON for dry-run mode.

    Delegates to devops_cli.output.
    """
    from devops_cli.output.console import render_dry_run_result as _render_output

    return _render_output(
        command=command,
        action=action,
        target=target,
        details=details,
    )

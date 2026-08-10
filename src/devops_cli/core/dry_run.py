"""Dry-run state and rendering helpers."""

from __future__ import annotations

import os
import shlex

_DRY_RUN_ENV = "DEVOPS_CLI_DRY_RUN"


def set_dry_run(enabled: bool) -> None:
    """Set global dry-run mode in environment."""
    if enabled:
        os.environ[_DRY_RUN_ENV] = "true"
        return
    os.environ.pop(_DRY_RUN_ENV, None)


def is_dry_run() -> bool:
    """Check if dry-run mode is enabled."""
    value = os.environ.get(_DRY_RUN_ENV, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def format_command(command: list[str], *, cwd: str | None = None) -> str:
    """Format shell command string for dry-run output."""
    rendered = shlex.join(command)
    if cwd:
        return f"(cd {shlex.quote(cwd)} && {rendered})"
    return rendered

"""Dry-run submodule: state management, command formatting, and response models."""

from __future__ import annotations

from typing import Any

from devops_cli.dry_run.state import (
    format_command,
    is_dry_run,
    is_dry_run_requested,
    render_dry_run_result,
    set_dry_run,
)


def __getattr__(name: str) -> Any:
    if name == "CommandDryRunResult":
        from devops_cli.dry_run.models import CommandDryRunResult

        return CommandDryRunResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CommandDryRunResult",
    "format_command",
    "is_dry_run",
    "is_dry_run_requested",
    "render_dry_run_result",
    "set_dry_run",
]

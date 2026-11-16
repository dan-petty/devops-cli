"""Dry-run submodule: state management, command formatting, and response models.

The names load on first access, so a CLI start that imports `devops_cli.dry_run.state` runs this
package without the pydantic models (#3550).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.dry_run.decorator import (
        CONST_DRY_RUN_CLASSES,
        dry_run_class,
        dry_run_command,
        get_dry_run_class,
    )
    from devops_cli.dry_run.models import CommandDryRunResult
    from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
    from devops_cli.dry_run.state import (
        dry_run_requested_by_environment,
        format_command,
        in_dry_run_invocation,
        is_dry_run,
        is_dry_run_requested,
        mark_dry_run_invocation,
        render_dry_run_result,
        set_dry_run,
    )

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "CONST_DRY_RUN_CLASSES": ("devops_cli.dry_run.decorator", "CONST_DRY_RUN_CLASSES"),
    "CommandDryRunResult": ("devops_cli.dry_run.models", "CommandDryRunResult"),
    "PlannedRequest": ("devops_cli.dry_run.requests", "PlannedRequest"),
    "dry_run_class": ("devops_cli.dry_run.decorator", "dry_run_class"),
    "dry_run_command": ("devops_cli.dry_run.decorator", "dry_run_command"),
    "dry_run_requested_by_environment": (
        "devops_cli.dry_run.state",
        "dry_run_requested_by_environment",
    ),
    "format_command": ("devops_cli.dry_run.state", "format_command"),
    "get_dry_run_class": ("devops_cli.dry_run.decorator", "get_dry_run_class"),
    "in_dry_run_invocation": ("devops_cli.dry_run.state", "in_dry_run_invocation"),
    "is_dry_run": ("devops_cli.dry_run.state", "is_dry_run"),
    "is_dry_run_requested": ("devops_cli.dry_run.state", "is_dry_run_requested"),
    "mark_dry_run_invocation": ("devops_cli.dry_run.state", "mark_dry_run_invocation"),
    "render_dry_run_result": ("devops_cli.dry_run.state", "render_dry_run_result"),
    "render_request_plan": ("devops_cli.dry_run.requests", "render_request_plan"),
    "set_dry_run": ("devops_cli.dry_run.state", "set_dry_run"),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CONST_DRY_RUN_CLASSES",
    "CommandDryRunResult",
    "PlannedRequest",
    "dry_run_class",
    "dry_run_command",
    "dry_run_requested_by_environment",
    "format_command",
    "get_dry_run_class",
    "in_dry_run_invocation",
    "is_dry_run",
    "is_dry_run_requested",
    "mark_dry_run_invocation",
    "render_dry_run_result",
    "render_request_plan",
    "set_dry_run",
]

"""Dry-run submodule: state management, command formatting, and response models."""

from __future__ import annotations

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

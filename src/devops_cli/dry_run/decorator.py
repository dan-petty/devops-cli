"""Declarative dry-run command decorator for devops-cli."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from devops_cli.dry_run.state import (
    is_dry_run,
    render_dry_run_result,
    set_dry_run,
)

F = TypeVar("F", bound=Callable[..., Any])


def dry_run_command(
    command: str,
    action: str,
    target_param: str | None = None,
    detail_params: list[str] | None = None,
) -> Callable[[F], F]:
    """Declarative decorator that intercepts dry-run invocations, renders formatted results,
    and bypasses destructive command execution without procedural boilerplate.

    Args:
        command: Canonical CLI command name (e.g. 'devops k8s deploy').
        action: Operational action descriptor (e.g. 'helm_install_or_upgrade').
        target_param: Name of parameter representing the operation target.
        detail_params: Names of parameters to collect into the execution details dictionary.
    """

    def decorator(fn: F) -> F:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            passed_dry_run = bool(bound.arguments.get("dry_run", False))
            active_dry_run = is_dry_run() or passed_dry_run

            if active_dry_run:
                set_dry_run(True)
                target = (
                    str(bound.arguments.get(target_param))
                    if target_param and bound.arguments.get(target_param) is not None
                    else None
                )
                details: dict[str, Any] = {}
                if detail_params:
                    for p in detail_params:
                        if p in bound.arguments:
                            details[p] = bound.arguments[p]
                render_dry_run_result(
                    command=command,
                    action=action,
                    target=target,
                    details=details,
                )
                return None

            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator

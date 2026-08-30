"""Universal declarative CLI command handler decorator for devops-cli."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

import typer

from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.output import print_error
from devops_cli.telemetry import record_metric, trace_span

F = TypeVar("F", bound=Callable[..., Any])


def _record_success_metrics(command_name: str, elapsed: float, record_metrics: bool) -> None:
    """Record duration and success counter metrics for a command."""
    if not record_metrics:
        return
    record_metric(
        "cli.command.duration_seconds",
        elapsed,
        attributes={"command": command_name, "status": "success"},
    )
    record_metric(
        "cli.command.total",
        1.0,
        attributes={"command": command_name, "status": "success"},
    )


def _record_error_metrics(
    command_name: str,
    record_metrics: bool,
    *,
    error_code: str | None = None,
    error_type: str | None = None,
) -> None:
    """Record error counter metric for a failed command."""
    if not record_metrics:
        return
    attrs: dict[str, Any] = {"command": command_name, "status": "error"}
    if error_code:
        attrs["error_code"] = error_code
    if error_type:
        attrs["error_type"] = error_type
    record_metric("cli.command.total", 1.0, attributes=attrs)


def cli_command_handler(
    command_name: str,
    *,
    record_metrics: bool = True,
    dry_run_supported: bool = True,
) -> Callable[[F], F]:
    """Universal declarative decorator wrapping CLI commands with tracing, metrics, and dry-run dispatch."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t_start = time.perf_counter()
            span_name = f"cli.command.{command_name}"

            with trace_span(
                span_name,
                attributes={
                    "cli.command": command_name,
                    "cli.dry_run": is_dry_run(),
                },
            ) as span_h:
                span_h.add_event("command_started", {"command": command_name})
                try:
                    res = fn(*args, **kwargs)
                    elapsed = time.perf_counter() - t_start
                    span_h.set_attribute("cli.elapsed_seconds", elapsed)
                    span_h.set_attribute("cli.success", True)
                    span_h.add_event("command_completed", {"elapsed_seconds": elapsed})
                    _record_success_metrics(command_name, elapsed, record_metrics)
                    return res

                except DevOpsCLIError as exc:
                    span_h.set_attribute("cli.success", False)
                    span_h.set_attribute("cli.exit_code", exc.exit_code)
                    span_h.record_exception(exc)
                    _record_error_metrics(command_name, record_metrics, error_code=exc.error_code)
                    print_error(f"[{exc.error_code}] {exc.message}", prefix=True)
                    raise typer.Exit(code=exc.exit_code) from exc

                except typer.Exit:
                    raise

                except Exception as exc:
                    span_h.set_attribute("cli.success", False)
                    span_h.record_exception(exc)
                    _record_error_metrics(
                        command_name, record_metrics, error_type=type(exc).__name__
                    )
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator

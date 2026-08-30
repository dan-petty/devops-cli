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

                    if record_metrics:
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

                    return res

                except DevOpsCLIError as exc:
                    elapsed = time.perf_counter() - t_start
                    span_h.set_attribute("cli.success", False)
                    span_h.set_attribute("cli.exit_code", exc.exit_code)
                    span_h.record_exception(exc)

                    if record_metrics:
                        record_metric(
                            "cli.command.total",
                            1.0,
                            attributes={
                                "command": command_name,
                                "status": "error",
                                "error_code": exc.error_code,
                            },
                        )

                    print_error(f"[{exc.error_code}] {exc.message}", prefix=True)
                    raise typer.Exit(code=exc.exit_code) from exc

                except typer.Exit:
                    raise

                except Exception as exc:
                    elapsed = time.perf_counter() - t_start
                    span_h.set_attribute("cli.success", False)
                    span_h.record_exception(exc)

                    if record_metrics:
                        record_metric(
                            "cli.command.total",
                            1.0,
                            attributes={
                                "command": command_name,
                                "status": "error",
                                "error_type": exc.__class__.__name__,
                            },
                        )
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator

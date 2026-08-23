"""CLI application creation helpers with OpenTelemetry command tracing."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from devops_cli.config.constants import CONST_HELP_OPTION_NAMES
from devops_cli.telemetry import record_metric, trace_span


class OTelTyper(typer.Typer):
    """Typer subclass that automatically traces all registered command executions."""

    def command(self, *args: Any, **kwargs: Any) -> Any:
        decorator = super().command(*args, **kwargs)

        def wrapper(f: Callable[..., Any]) -> Any:
            cmd_name = kwargs.get("name") or getattr(f, "__name__", "command").replace("_", "-")

            @functools.wraps(f)
            def traced_fn(*f_args: Any, **f_kwargs: Any) -> Any:
                span_name = f"cli.{cmd_name}"
                t0 = time.perf_counter()
                with trace_span(
                    span_name,
                    attributes={
                        "cli.command": cmd_name,
                        "cli.function": getattr(f, "__qualname__", str(f)),
                    },
                ) as span_h:
                    try:
                        res = f(*f_args, **f_kwargs)
                        dur = time.perf_counter() - t0
                        span_h.set_attribute("cli.duration_seconds", dur)
                        span_h.set_attribute("cli.status", "ok")
                        record_metric(
                            "devops_cli_subcommand_seconds",
                            dur,
                            unit="s",
                            attributes={"command": cmd_name, "status": "ok"},
                        )
                        return res
                    except Exception as exc:
                        dur = time.perf_counter() - t0
                        span_h.set_attribute("cli.duration_seconds", dur)
                        span_h.set_attribute("cli.status", "error")
                        span_h.set_attribute("cli.error", str(exc))
                        record_metric(
                            "devops_cli_subcommand_seconds",
                            dur,
                            unit="s",
                            attributes={"command": cmd_name, "status": "error"},
                        )
                        raise

            return decorator(traced_fn)

        return wrapper


def new_typer(**kwargs: Any) -> typer.Typer:
    """Create an OTel-instrumented Typer app with consistent help option names."""
    context_settings = dict(kwargs.pop("context_settings", {}))
    context_settings.setdefault("help_option_names", list(CONST_HELP_OPTION_NAMES))
    return OTelTyper(context_settings=context_settings, **kwargs)


def repo_label(repo_dir: Path) -> str:
    """Return the "<group>/<repo>" display label for a cloned repository directory."""
    return f"{repo_dir.parent.name}/{repo_dir.name}"

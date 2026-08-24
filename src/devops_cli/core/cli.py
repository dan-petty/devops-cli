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
                kwargs_summary = ", ".join(f_kwargs.keys()) if f_kwargs else ""
                with trace_span(
                    span_name,
                    attributes={
                        "cli.command": cmd_name,
                        "cli.function": getattr(f, "__qualname__", str(f)),
                        "cli.args_count": len(f_args),
                        "cli.kwargs_keys": kwargs_summary,
                    },
                ) as span_h:
                    span_h.add_event("subcommand_started", {"command": cmd_name})
                    try:
                        res = f(*f_args, **f_kwargs)
                        dur = time.perf_counter() - t0
                        span_h.set_attribute("cli.duration_seconds", dur)
                        span_h.set_attribute("cli.status", "ok")
                        span_h.add_event(
                            "subcommand_completed",
                            {"command": cmd_name, "duration_seconds": dur},
                        )
                        record_metric(
                            "devops_cli_subcommand_seconds",
                            dur,
                            unit="s",
                            attributes={"command": cmd_name, "status": "ok"},
                        )
                        return res
                    except Exception as exc:
                        dur = time.perf_counter() - t0
                        exit_code = getattr(exc, "exit_code", getattr(exc, "code", None))
                        is_clean_exit = exit_code == 0
                        status_str = "ok" if is_clean_exit else "error"
                        span_h.set_attribute("cli.duration_seconds", dur)
                        span_h.set_attribute("cli.status", status_str)
                        if exit_code is not None:
                            span_h.set_attribute("cli.exit_code", exit_code)

                        if is_clean_exit:
                            span_h.add_event(
                                "subcommand_completed",
                                {"command": cmd_name, "duration_seconds": dur, "exit_code": 0},
                            )
                            record_metric(
                                "devops_cli_subcommand_seconds",
                                dur,
                                unit="s",
                                attributes={"command": cmd_name, "status": "ok"},
                            )
                        else:
                            span_h.set_attribute("cli.error", str(exc))
                            span_h.add_event(
                                "subcommand_failed",
                                {"command": cmd_name, "error": str(exc)},
                            )
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

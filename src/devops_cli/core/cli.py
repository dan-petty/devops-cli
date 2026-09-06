"""CLI application creation helpers with OpenTelemetry command tracing."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import typer

from devops_cli.config.constants import CONST_HELP_OPTION_NAMES


def _record_cli_success(span_h: Any, cmd_name: str, dur: float) -> None:
    """Record telemetry attributes, events, and metrics for successful CLI command execution."""
    from devops_cli.telemetry import record_metric

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


def _record_cli_failure(span_h: Any, cmd_name: str, dur: float, exc: Exception) -> None:
    """Record telemetry attributes, events, and metrics for failed or exiting CLI command."""
    exit_code = getattr(exc, "exit_code", getattr(exc, "code", None))
    is_clean_exit = exit_code == 0
    status_str = "ok" if is_clean_exit else "error"
    span_h.set_attribute("cli.duration_seconds", dur)
    span_h.set_attribute("cli.status", status_str)
    if exit_code is not None:
        span_h.set_attribute("cli.exit_code", exit_code)

    from devops_cli.telemetry import record_metric

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
        from devops_cli.ai.review.sanitization import _mask_secrets_in_content

        clean_err = _mask_secrets_in_content(str(exc))
        span_h.set_attribute("cli.error", clean_err)
        span_h.add_event(
            "subcommand_failed",
            {"command": cmd_name, "error": clean_err},
        )
        record_metric(
            "devops_cli_subcommand_seconds",
            dur,
            unit="s",
            attributes={"command": cmd_name, "status": "error"},
        )


def _execute_traced_cli_command(
    f: Callable[..., Any],
    f_args: tuple[Any, ...],
    f_kwargs: dict[str, Any],
    cmd_name: str,
) -> Any:
    """Execute CLI subcommand wrapped in OpenTelemetry span with telemetry recording."""
    from devops_cli.telemetry import trace_span

    span_name = f"cli.{cmd_name}"
    t0 = time.perf_counter()
    kwargs_summary = ", ".join(f_kwargs.keys()) if f_kwargs else ""
    attrs = {
        "cli.command": cmd_name,
        "cli.function": getattr(f, "__qualname__", str(f)),
        "cli.args_count": len(f_args),
        "cli.kwargs_keys": kwargs_summary,
    }
    with trace_span(span_name, attributes=attrs) as span_h:
        span_h.add_event("subcommand_started", {"command": cmd_name})
        try:
            res = f(*f_args, **f_kwargs)
            _record_cli_success(span_h, cmd_name, time.perf_counter() - t0)
            return res
        except Exception as exc:
            _record_cli_failure(span_h, cmd_name, time.perf_counter() - t0, exc)
            raise


_CommandFunc = TypeVar("_CommandFunc", bound=Callable[..., Any])


class OTelTyper(typer.Typer):
    """Subclass of Typer that wraps every registered command in an OpenTelemetry trace span and supports lazy string module paths."""

    def add_typer(
        self,
        typer_instance: typer.Typer | str,
        *args: Any,
        name: str | None = None,
        help: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Register a sub-typer, supporting both eager Typer instances and lazy string paths ('pkg.mod:app')."""
        if isinstance(typer_instance, str):
            target = typer_instance
            cmd_name = name or target.rpartition(".")[2].partition(":")[0]
            help_text = help or ""

            def _lazy_proxy(ctx: typer.Context) -> None:
                from devops_cli.dry_run import is_dry_run

                if is_dry_run():
                    args = ["devops", cmd_name, *list(ctx.args)]
                    from devops_cli.output import print_dry_run_command

                    print_dry_run_command(args, delegated=True)
                    return

                from devops_cli.main import _delegate

                mod_path, _, _ = target.partition(":")
                _delegate(mod_path, cmd_name, list(ctx.args))

            self.command(
                name=cmd_name,
                help=help_text,
                add_help_option=False,
                context_settings={
                    "allow_extra_args": True,
                    "ignore_unknown_options": True,
                },
            )(_lazy_proxy)

            return None
        return super().add_typer(typer_instance, *args, name=name, help=help, **kwargs)

    def command(self, *args: Any, **kwargs: Any) -> Callable[[_CommandFunc], _CommandFunc]:
        decorator = super().command(*args, **kwargs)

        def wrapper(f: _CommandFunc) -> _CommandFunc:
            cmd_name = kwargs.get("name") or getattr(f, "__name__", "command").replace("_", "-")

            @functools.wraps(f)
            def traced_fn(*f_args: Any, **f_kwargs: Any) -> Any:
                return _execute_traced_cli_command(f, f_args, f_kwargs, cmd_name)

            decorator(traced_fn)
            return f

        return wrapper


def new_typer(**kwargs: Any) -> OTelTyper:
    """Create an OTel-instrumented Typer app with consistent help option names."""
    context_settings = dict(kwargs.pop("context_settings", {}))
    context_settings.setdefault("help_option_names", list(CONST_HELP_OPTION_NAMES))
    return OTelTyper(context_settings=context_settings, **kwargs)


def repo_label(repo_dir: Path) -> str:
    """Return the "<group>/<repo>" display label for a cloned repository directory."""
    return f"{repo_dir.parent.name}/{repo_dir.name}"

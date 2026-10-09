"""CLI application creation helpers with OpenTelemetry command tracing."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

import typer

from devops_cli.config.constants import CONST_HELP_OPTION_NAMES
from devops_cli.exceptions.base import DevOpsCLIError


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
        from devops_cli.security.sanitizer import mask_secrets

        clean_err = mask_secrets(str(exc))
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
    start_time = time.perf_counter()
    kwargs_summary = ", ".join(f_kwargs.keys()) if f_kwargs else ""
    func_name = getattr(f, "__qualname__", getattr(f, "__name__", str(f)))
    module_name = getattr(f, "__module__", "")
    attrs = {
        "cli.command": cmd_name,
        "code.function": func_name,
        "code.namespace": module_name,
        "cli.args_count": len(f_args),
        "cli.kwargs_keys": kwargs_summary,
    }
    with trace_span(span_name, attributes=attrs) as span_h:
        span_h.add_event("subcommand_started", {"command": cmd_name})
        try:
            res = f(*f_args, **f_kwargs)
            _record_cli_success(span_h, cmd_name, time.perf_counter() - start_time)
            return res
        except Exception as exc:
            _record_cli_failure(span_h, cmd_name, time.perf_counter() - start_time, exc)
            raise


_CommandFunc = TypeVar("_CommandFunc", bound=Callable[..., Any])


def _handle_lazy_proxy_dry_run(target: str, cmd_name: str, args: list[str]) -> None:
    """Handle delegated command proxy routing under dry-run mode."""
    own_args = args[: args.index("--")] if "--" in args else args
    from devops_cli.main import _delegate

    mod_path, _, _ = target.partition(":")
    if any(a in ("-h", "--help") for a in own_args):
        _delegate(mod_path, cmd_name, args)
        return

    import click
    import typer._click.exceptions as click_exc

    from devops_cli.core.command_resolver import resolve_proxy_dry_run

    try:
        declares_dry_run, forwarded_args = resolve_proxy_dry_run(mod_path, cmd_name, args)
    except (click_exc.ClickException, click.ClickException) as exc:
        exc.show()
        raise typer.Exit(getattr(exc, "exit_code", 2)) from exc

    if declares_dry_run and forwarded_args is not None:
        _delegate(mod_path, cmd_name, forwarded_args)
        return

    from devops_cli.output import print_dry_run_command

    print_dry_run_command(["devops", cmd_name, *args], delegated=True)


class OTelTyper(typer.Typer):
    """Subclass of Typer that wraps every registered command in an OpenTelemetry trace span and supports lazy string module paths.

    With `exit_on`, each of its commands reports that error as `exit_on_error` does, without a
    traceback.
    """

    def __init__(self, *args: Any, exit_on: type[DevOpsCLIError] | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._exit_on = exit_on

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
                    _handle_lazy_proxy_dry_run(target, cmd_name, list(ctx.args))
                    return

                from devops_cli.main import _delegate

                mod_path, _, _ = target.partition(":")
                _delegate(mod_path, cmd_name, list(ctx.args))

            # Interspersed parsing would consume a `--` while collecting the extra arguments,
            # and the delegated command would then parse what followed it as options (#980).
            super().command(
                name=cmd_name,
                help=help_text,
                add_help_option=False,
                context_settings={
                    "allow_extra_args": True,
                    "allow_interspersed_args": False,
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
                if self._exit_on is None:
                    return _execute_traced_cli_command(f, f_args, f_kwargs, cmd_name)
                with exit_on_error(self._exit_on):
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


@contextmanager
def exit_on_error(error_type: type[DevOpsCLIError]) -> Iterator[None]:
    """Report an `error_type` raised in the block as the command's error and exit with its status.

    The error's own message is the report, printed without a traceback and with any Rich markup
    in it escaped, since it can quote a remote service's reply.
    """
    try:
        yield
    except error_type as exc:
        from devops_cli.output import print_error

        print_error(exc.message, safe=True)
        raise typer.Exit(exc.exit_code) from exc

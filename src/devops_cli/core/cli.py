"""CLI application creation helpers with OpenTelemetry command tracing."""

from __future__ import annotations

import functools
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

import typer

from devops_cli.config.constants import CONST_HELP_OPTION_NAMES
from devops_cli.exceptions.base import DevOpsCLIError


def _subcommand_labels(cmd_name: str, command_path: str | None) -> dict[str, str]:
    """The command group and the sub-command that `devops_cli_subcommand_duration_seconds` is sent by.

    Click's command path, such as `devops pr threads reply`, gives the command group (`pr`) and
    the path below `devops` (`pr threads reply`). Leaf names repeat across groups (`config list`,
    `pr list`), so the dashboard reads the full path (#2700). A command with no group above it
    names itself in both labels.
    """
    words = (command_path or "").split()[1:]
    if not words:
        return {"command": cmd_name, "sub_command": cmd_name}
    return {"command": words[0], "sub_command": " ".join(words)}


def _record_cli_success(span_h: Any, cmd_name: str, labels: dict[str, str], dur: float) -> None:
    """Record telemetry attributes, events, and metrics for successful CLI command execution."""
    from devops_cli.telemetry.instruments import SUBCOMMAND_DURATION, emit

    span_h.set_attribute("cli.duration_seconds", dur)
    span_h.set_attribute("cli.status", "ok")
    span_h.add_event(
        "subcommand_completed",
        {"command": cmd_name, "duration_seconds": dur},
    )
    emit(SUBCOMMAND_DURATION, dur, {**labels, "status": "ok"})


def _record_cli_failure(
    span_h: Any, cmd_name: str, labels: dict[str, str], dur: float, exc: Exception
) -> None:
    """Record telemetry attributes, events, and metrics for failed or exiting CLI command."""
    exit_code = getattr(exc, "exit_code", getattr(exc, "code", None))
    is_clean_exit = exit_code == 0
    status_str = "ok" if is_clean_exit else "error"
    span_h.set_attribute("cli.duration_seconds", dur)
    span_h.set_attribute("cli.status", status_str)
    if exit_code is not None:
        span_h.set_attribute("cli.exit_code", exit_code)

    from devops_cli.telemetry.instruments import SUBCOMMAND_DURATION, emit

    if is_clean_exit:
        span_h.add_event(
            "subcommand_completed",
            {"command": cmd_name, "duration_seconds": dur, "exit_code": 0},
        )
        emit(SUBCOMMAND_DURATION, dur, {**labels, "status": "ok"})
    else:
        if isinstance(exc, typer.TyperException):
            # A usage error of Typer, such as `typer.BadParameter`, quotes what the person typed,
            # and an argument can be a credential. The span records its class and no message, as
            # the tracer does (#2024).
            detail = {"error.type": exc.__class__.__name__}
        else:
            from devops_cli.security.sanitizer import mask_secrets

            detail = {"error": mask_secrets(str(exc))}
            span_h.set_attribute("cli.error", detail["error"])
        span_h.add_event("subcommand_failed", {"command": cmd_name, **detail})
        emit(SUBCOMMAND_DURATION, dur, {**labels, "status": "error"})


def _execute_traced_cli_command(
    f: Callable[..., Any],
    f_args: tuple[Any, ...],
    f_kwargs: dict[str, Any],
    cmd_name: str,
) -> Any:
    """Execute CLI subcommand wrapped in OpenTelemetry span with telemetry recording.

    The span names the parameters and holds no parameter value, as the command span of
    `main._delegate` does (#1996). Click's command path, such as `devops config set`, names the
    command that runs: it holds the command names and no argument.
    """
    from typer._click.globals import get_current_context

    from devops_cli.telemetry import trace_span

    span_name = f"cli.{cmd_name}"
    start_time = time.perf_counter()
    kwargs_summary = ", ".join(f_kwargs.keys()) if f_kwargs else ""
    func_name = getattr(f, "__qualname__", getattr(f, "__name__", str(f)))
    module_name = getattr(f, "__module__", "")
    attrs: dict[str, Any] = {
        "cli.command": cmd_name,
        "code.function": func_name,
        "code.namespace": module_name,
        "cli.args_count": len(f_args),
        "cli.kwargs_keys": kwargs_summary,
    }
    context = get_current_context(silent=True)
    if context is not None:
        attrs["cli.command_path"] = context.command_path
    labels = _subcommand_labels(cmd_name, context.command_path if context is not None else None)
    with trace_span(span_name, attributes=attrs) as span_h:
        span_h.add_event("subcommand_started", {"command": cmd_name})
        try:
            res = f(*f_args, **f_kwargs)
            _record_cli_success(span_h, cmd_name, labels, time.perf_counter() - start_time)
            return res
        except Exception as exc:
            _record_cli_failure(span_h, cmd_name, labels, time.perf_counter() - start_time, exc)
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

    It is the one exit seam of the CLI (#2487): each of its commands and callbacks reports a
    `DevOpsCLIError` that it raises as `_report_devops_error` does, without a traceback.
    """

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
                # Check if the working directory still exists before running any command
                try:
                    os.getcwd()
                except FileNotFoundError:
                    # The working directory no longer exists - stop with one error line
                    raise DevOpsCLIError(
                        "The working directory does not exist. Change to a directory that exists and run the command again.",
                        exit_code=1,
                    ) from None

                with _report_devops_error():
                    return _execute_traced_cli_command(f, f_args, f_kwargs, cmd_name)

            decorator(traced_fn)
            return f

        return wrapper

    def callback(self, *args: Any, **kwargs: Any) -> Callable[[_CommandFunc], _CommandFunc]:
        decorator = super().callback(*args, **kwargs)

        def wrapper(f: _CommandFunc) -> _CommandFunc:
            # A callback with `invoke_without_command=True` is the body of its command.
            @functools.wraps(f)
            def reported_fn(*f_args: Any, **f_kwargs: Any) -> Any:
                with _report_devops_error():
                    return f(*f_args, **f_kwargs)

            decorator(reported_fn)
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
def _report_devops_error() -> Iterator[None]:
    """Report a `DevOpsCLIError` raised in the block as the command's error and exit with its status.

    The error's own message is the report, printed without a traceback and with any Rich markup
    in it escaped, since it can quote a remote service's reply.
    """
    try:
        yield
    except DevOpsCLIError as exc:
        from devops_cli.output import print_error

        print_error(exc.message, safe=True)
        raise typer.Exit(exc.exit_code) from exc

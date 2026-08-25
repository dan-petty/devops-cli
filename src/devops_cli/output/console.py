"""Centralized terminal stream output, styled messaging, and console management."""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table


def get_console() -> Console:
    """Return a Rich Console instance dynamically bound to current standard output."""
    return Console()


def get_stderr_console() -> Console:
    """Return a Rich Console instance dynamically bound to current standard error."""
    return Console(stderr=True)


def write_stdout(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard output stream."""
    sys.stdout.write(text)
    if flush:
        sys.stdout.flush()


def write_stderr(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard error stream."""
    sys.stderr.write(text)
    if flush:
        sys.stderr.flush()


def print_success(
    message: str,
    *,
    prefix: bool = True,
    console: Console | None = None,
) -> None:
    """Print a success message with green styling."""
    c = console or get_console()
    pre = "✓ " if prefix else ""
    c.print(f"[bold green]{pre}{message}[/bold green]")


def print_error(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Console | None = None,
) -> None:
    """Print an error message with red styling."""
    c = console or (get_stderr_console() if to_stderr else get_console())
    pre = "✗ " if prefix else ""
    c.print(f"[bold red]{pre}{message}[/bold red]")


def print_warning(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Console | None = None,
) -> None:
    """Print a warning message with yellow styling."""
    c = console or (get_stderr_console() if to_stderr else get_console())
    pre = "! " if prefix else ""
    c.print(f"[yellow]{pre}{message}[/yellow]")


def print_info(
    message: str,
    *,
    prefix: bool = True,
    console: Console | None = None,
) -> None:
    """Print an informational message with cyan styling."""
    c = console or get_console()
    pre = "ℹ " if prefix else ""
    c.print(f"[cyan]{pre}{message}[/cyan]")


def print_muted(
    message: str,
    *,
    to_stderr: bool = False,
    console: Console | None = None,
) -> None:
    """Print a muted/dim message."""
    c = console or (get_stderr_console() if to_stderr else get_console())
    c.print(f"[dim]{message}[/dim]")


def print_step(
    step: str,
    detail: str = "",
    *,
    console: Console | None = None,
) -> None:
    """Print a structured execution step."""
    c = console or get_console()
    detail_str = f" [dim]({detail})[/dim]" if detail else ""
    c.print(f"[bold blue]➔[/bold blue] [bold]{step}[/bold]{detail_str}")


def print_panel(
    renderable: RenderableType,
    *,
    title: str | None = None,
    border_style: str = "cyan",
    console: Console | None = None,
    **kwargs: Any,
) -> None:
    """Render and print a styled Rich Panel."""
    c = console or get_console()
    c.print(Panel(renderable, title=title, border_style=border_style, **kwargs))


def print_table(
    table: Table,
    *,
    console: Console | None = None,
) -> None:
    """Print a Rich Table to the console."""
    c = console or get_console()
    c.print(table)


def print_dry_run_command(
    command: list[str] | str,
    *,
    cwd: str | None = None,
    delegated: bool = False,
    console: Console | None = None,
) -> None:
    """Print formatted dry-run simulated command execution message."""
    import shlex

    from devops_cli.lang.en.messages import MESSAGES

    c = console or get_console()
    if isinstance(command, list):
        rendered = shlex.join(command)
        if cwd:
            rendered = f"(cd {shlex.quote(cwd)} && {rendered})"
    else:
        rendered = command

    msg_template = (
        MESSAGES.dry_run.would_run_delegated if delegated else MESSAGES.dry_run.would_run_command
    )
    c.print(msg_template.format(command=rendered))


def print_dry_run_result(
    result: Any,
    *,
    console: Console | None = None,
) -> None:
    """Print structured CommandDryRunResult JSON for dry-run mode."""
    from devops_cli.lang.en.messages import MESSAGES

    c = console or get_console()
    c.print(MESSAGES.dry_run.command_response_header)
    dump_fn = getattr(result, "model_dump_json", None)
    if callable(dump_fn):
        c.print_json(dump_fn(indent=2))
    elif isinstance(result, str):
        c.print_json(result)
    else:
        import json

        c.print_json(json.dumps(result, indent=2, default=str))


def render_dry_run_result(
    command: str,
    action: str = "",
    target: str | None = None,
    details: dict[str, Any] | None = None,
    *,
    console: Console | None = None,
) -> Any:
    """Construct, print, and return structured CommandDryRunResult JSON for dry-run mode."""
    from devops_cli.dry_run.models import CommandDryRunResult

    res = CommandDryRunResult(
        command=command,
        action=action or "",
        target=target,
        details=details or {},
    )
    print_dry_run_result(res, console=console)
    return res

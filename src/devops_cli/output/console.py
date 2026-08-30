"""Centralized terminal stream output, styled messaging, and console management."""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator, Iterable, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console as _RichConsole
from rich.console import RenderableType as _RichRenderableType
from rich.markdown import Markdown as _RichMarkdown
from rich.markup import escape as _rich_escape
from rich.panel import Panel as _RichPanel
from rich.progress import (
    BarColumn as _RichBarColumn,
)
from rich.progress import (
    Progress as _RichProgress,
)
from rich.progress import (
    SpinnerColumn as _RichSpinnerColumn,
)
from rich.progress import (
    TextColumn as _RichTextColumn,
)
from rich.progress import (
    track as _rich_track,
)
from rich.rule import Rule as _RichRule
from rich.syntax import Syntax as _RichSyntax
from rich.table import Table as _RichTable

from devops_cli.config.constants import CONST_DEFAULT_LINE_NUMBER
from devops_cli.config.defaults import (
    DEFAULT_KEY_STYLE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PANEL_BORDER_STYLE,
    DEFAULT_PROGRESS_DESC_PROCESSING,
    DEFAULT_PROGRESS_DESC_WORKING,
    DEFAULT_PROGRESS_TOTAL,
    DEFAULT_STREAM_NAME,
    DEFAULT_SYNTAX_LANGUAGE,
    DEFAULT_SYNTAX_THEME,
    DEFAULT_TABLE_BORDER_STYLE,
    DEFAULT_VALUE_STYLE,
)

if TYPE_CHECKING:
    from devops_cli.output.models import (
        MarkdownPayload,
        MessageLevel,
        PanelPayload,
        RulePayload,
        SyntaxPayload,
        TablePayload,
    )

# Shared Console instance for standard output
_CONSOLE: _RichConsole | None = None
_STDERR_CONSOLE: _RichConsole | None = None


def get_console(
    *,
    file: Any = None,
    color_system: Any = None,
    stderr: bool = False,
    force_terminal: bool | None = None,
    **kwargs: Any,
) -> _RichConsole:
    """Return a Console instance dynamically bound to output, stderr, or custom file stream."""
    global _CONSOLE, _STDERR_CONSOLE
    if file is not None or kwargs or force_terminal is not None or color_system is not None:
        return _RichConsole(
            file=file,
            color_system=color_system,
            stderr=stderr,
            force_terminal=force_terminal,
            **kwargs,
        )
    if stderr:
        if _STDERR_CONSOLE is None:
            _STDERR_CONSOLE = _RichConsole(stderr=True)
        return _STDERR_CONSOLE
    if _CONSOLE is None:
        _CONSOLE = _RichConsole()
    return _CONSOLE


def get_stderr_console(
    *,
    file: Any = None,
    color_system: Any = None,
    force_terminal: bool | None = None,
    **kwargs: Any,
) -> _RichConsole:
    """Return a Console instance dynamically bound to standard error stream."""
    return get_console(
        file=file, color_system=color_system, stderr=True, force_terminal=force_terminal, **kwargs
    )


def _sanitize_output_text(text: str) -> str:
    """Ensure raw text is safely formatted before emitting to standard output or error streams."""
    return str(text) if text is not None else ""


def write_stream(
    text: str,
    stream: Literal["stdout", "stderr"] = DEFAULT_STREAM_NAME,  # type: ignore[assignment]
    *,
    flush: bool = True,
) -> None:
    """Write raw text directly to standard output or standard error stream."""
    safe_text = _sanitize_output_text(text)
    target = sys.stderr if stream == "stderr" else sys.stdout
    target.write(safe_text)
    if flush:
        target.flush()


def write_stdout(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard output stream."""
    write_stream(text, stream="stdout", flush=flush)


def write_stderr(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard error stream."""
    write_stream(text, stream="stderr", flush=flush)


def escape_text(text: str) -> str:
    """Escape Rich markup tags in string."""
    return _rich_escape(text)


def print_message(
    message: str,
    *,
    level: MessageLevel = DEFAULT_LOG_LEVEL,  # type: ignore[assignment]
    prefix: bool | str = True,
    to_stderr: bool = False,
    style: str | None = None,
    console: Any = None,
) -> None:
    """Print a styled, leveled console message with optional prefix and stream targeting.

    Args:
        message: Text content to print.
        level: Message level ('success', 'error', 'warning', 'info', 'muted', 'step', or 'raw').
        prefix: Whether to include default level prefix icon, or a custom prefix string.
        to_stderr: Target stderr stream instead of stdout.
        style: Optional Rich markup style override.
        console: Optional existing Rich Console instance.
    """
    effective_stderr = to_stderr or (level == "error")
    c = console or (get_stderr_console() if effective_stderr else get_console())

    if level == "raw":
        c.print(message)
        return

    defaults: dict[str, tuple[str, str]] = {
        "success": ("bold green", "✓ "),
        "error": ("bold red", "✗ "),
        "warning": ("yellow", "! "),
        "info": ("cyan", "ℹ "),
        "muted": ("dim", ""),
        "step": ("bold blue", "➔ "),
    }

    def_style, def_prefix = defaults.get(level, ("white", ""))

    if isinstance(prefix, str):
        pre_str = prefix
    elif prefix:
        pre_str = def_prefix
    else:
        pre_str = ""

    if style is not None:
        c.print(f"[{style}]{pre_str}{message}[/{style}]")
    elif prefix:
        if level == "info":
            c.print(f"[{def_style}]{pre_str}[/{def_style}]{message}")
        else:
            c.print(f"[{def_style}]{pre_str}{message}[/{def_style}]")
    else:
        if level in {"error", "warning", "muted", "success", "step"}:
            c.print(f"[{def_style}]{message}[/{def_style}]")
        else:
            c.print(message)


def print_success(
    message: str,
    *,
    prefix: bool = True,
    console: Any = None,
) -> None:
    """Print a success message with green styling."""
    print_message(message, level="success", prefix=prefix, console=console)


def print_error(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print an error message with red styling."""
    print_message(message, level="error", prefix=prefix, to_stderr=to_stderr, console=console)


def print_warning(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print a warning message with yellow styling."""
    print_message(message, level="warning", prefix=prefix, to_stderr=to_stderr, console=console)


def print_info(
    message: str,
    *,
    prefix: bool = True,
    console: Any = None,
) -> None:
    """Print an informational message with cyan styling."""
    print_message(message, level="info", prefix=prefix, console=console)


def print_muted(
    message: str,
    *,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print a muted/dim message."""
    print_message(message, level="muted", prefix=False, to_stderr=to_stderr, console=console)


def print_step(
    step: str,
    detail: str = "",
    *,
    console: Any = None,
) -> None:
    """Print a structured execution step."""
    c = console or get_console()
    detail_str = f" [dim]({detail})[/dim]" if detail else ""
    c.print(f"[bold blue]➔[/bold blue] [bold]{step}[/bold]{detail_str}")


def print_section(
    title: str | RulePayload = "",
    *,
    style: str = DEFAULT_KEY_STYLE,
    console: Any = None,
) -> None:
    """Print a styled section rule divider."""
    c = console or get_console()
    if hasattr(title, "render"):
        c.print(title.render())
        return
    c.print(_RichRule(str(title), style=style))


def print_markdown(
    markdown_text: str | MarkdownPayload,
    *,
    console: Any = None,
) -> None:
    """Render and print markdown text."""
    c = console or get_console()
    if hasattr(markdown_text, "render"):
        c.print(markdown_text.render())
        return
    c.print(_RichMarkdown(str(markdown_text)))


def print_syntax(
    code: str | SyntaxPayload,
    language: str = DEFAULT_SYNTAX_LANGUAGE,
    *,
    line_numbers: bool = False,
    start_line: int = CONST_DEFAULT_LINE_NUMBER,
    theme: str = DEFAULT_SYNTAX_THEME,
    console: Any = None,
    **kwargs: Any,
) -> None:
    """Render and print syntax-highlighted code."""
    c = console or get_console()
    if hasattr(code, "render"):
        c.print(code.render())
        return
    c.print(
        _RichSyntax(
            str(code),
            language,
            line_numbers=line_numbers,
            start_line=start_line,
            theme=theme,
            **kwargs,
        )
    )


def print_panel(
    renderable: _RichRenderableType | PanelPayload | str,
    *,
    title: str | None = None,
    border_style: str = DEFAULT_PANEL_BORDER_STYLE,
    console: Any = None,
    **kwargs: Any,
) -> None:
    """Render and print a styled Panel."""
    c = console or get_console()
    if hasattr(renderable, "render") and not isinstance(renderable, _RichPanel):
        c.print(renderable.render())
        return
    c.print(_RichPanel(renderable, title=title, border_style=border_style, **kwargs))


def print_table(
    table_or_title: TablePayload | _RichTable | Any = "",
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
    *,
    title: str | None = None,
    border_style: str | None = DEFAULT_TABLE_BORDER_STYLE,
    box_style: Any = None,
    console: Any = None,
) -> None:
    """Render and print a styled table to the console.

    Can be called with an existing Rich Table, a TablePayload, a KeyValuePayload,
    or with standard (title, columns, rows).
    """
    c = console or get_console()

    if isinstance(table_or_title, _RichTable):
        c.print(table_or_title)
        return

    if hasattr(table_or_title, "render"):
        c.print(table_or_title.render())
        return

    from devops_cli.output.formatter import render_table

    tbl = render_table(
        title=title or table_or_title,
        columns=columns or [],
        rows=rows or [],
        border_style=border_style,
        box_style=box_style,
    )
    c.print(tbl)


def print_key_values(
    title: str,
    items: dict[str, Any] | list[tuple[str, Any]],
    *,
    key_style: str = DEFAULT_KEY_STYLE,
    value_style: str = DEFAULT_VALUE_STYLE,
    console: Any = None,
) -> None:
    """Render and print a key-value summary table to the console."""
    rows: list[list[str]] = []
    pairs = items.items() if isinstance(items, dict) else items
    for k, v in pairs:
        rows.append([str(k), str(v)])
    print_table(
        table_or_title=title,
        columns=[("Property", key_style), ("Value", value_style)],
        rows=rows,
        console=console,
    )


def track_progress[T](
    iterable: Iterable[T],
    description: str = DEFAULT_PROGRESS_DESC_WORKING,
    *,
    console: Any = None,
) -> Generator[T]:
    """Iterate with Rich progress bar tracking."""
    c = console or get_console()
    yield from _rich_track(iterable, description=description, console=c)


def print_syntax_panel(
    code: str | SyntaxPayload,
    language: str = DEFAULT_SYNTAX_LANGUAGE,
    *,
    title: str | None = None,
    border_style: str = DEFAULT_PANEL_BORDER_STYLE,
    line_numbers: bool = True,
    start_line: int = CONST_DEFAULT_LINE_NUMBER,
    theme: str = DEFAULT_SYNTAX_THEME,
    console: Any = None,
) -> None:
    """Render syntax-highlighted code inside a styled panel."""
    c = console or get_console()
    syntax = (
        code.render()
        if hasattr(code, "render")
        else _RichSyntax(
            str(code),
            language,
            line_numbers=line_numbers,
            start_line=start_line,
            theme=theme,
        )
    )
    c.print(_RichPanel(syntax, title=title, border_style=border_style))


@contextmanager
def progress_context(
    description: str = DEFAULT_PROGRESS_DESC_PROCESSING,
    *,
    total: float = DEFAULT_PROGRESS_TOTAL,
    console: Any = None,
) -> Generator[Callable[[str, float], None]]:
    """Context manager providing a styled progress bar with an update callback.

    Yields:
        update_fn(description: str, completed: float)
    """
    c = console or get_console()
    with _RichProgress(
        _RichSpinnerColumn(),
        _RichTextColumn("[progress.description]{task.description}"),
        _RichBarColumn(),
        _RichTextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=c,
    ) as progress:
        task_id = progress.add_task(description, total=total)

        def _update(desc: str, completed: float) -> None:
            progress.update(task_id, description=desc, completed=completed)

        yield _update


def _sanitize_command_args_for_display(command: list[str]) -> list[str]:
    """Mask sensitive argument values in command list before terminal printing."""
    sanitized: list[str] = []
    skip_next = False
    for arg in command:
        if skip_next:
            sanitized.append("<masked>")
            skip_next = False
            continue
        if arg in ("--password", "-p", "--token", "--api-key", "--secret", "--auth-token"):
            sanitized.append(arg)
            skip_next = True
        elif any(
            arg.startswith(prefix)
            for prefix in ("--password=", "--token=", "--api-key=", "--secret=", "--auth-token=")
        ):
            key = arg.split("=", 1)[0]
            sanitized.append(f"{key}=<masked>")
        else:
            sanitized.append(arg)
    return sanitized


def print_dry_run_command(
    command: list[str] | str,
    *,
    cwd: str | None = None,
    delegated: bool = False,
    console: Any = None,
) -> None:
    """Print formatted dry-run simulated command execution message."""
    import shlex

    from devops_cli.lang.en.messages import MESSAGES

    c = console or get_console()
    if isinstance(command, list):
        safe_cmd = _sanitize_command_args_for_display(command)
        rendered = shlex.join(safe_cmd)
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
    console: Any = None,
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
    console: Any = None,
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


__all__ = [
    "MessageLevel",
    "escape_text",
    "get_console",
    "get_stderr_console",
    "print_dry_run_command",
    "print_dry_run_result",
    "print_error",
    "print_info",
    "print_key_values",
    "print_markdown",
    "print_message",
    "print_muted",
    "print_panel",
    "print_section",
    "print_step",
    "print_success",
    "print_syntax",
    "print_syntax_panel",
    "print_table",
    "print_warning",
    "progress_context",
    "render_dry_run_result",
    "track_progress",
    "write_stderr",
    "write_stdout",
    "write_stream",
]

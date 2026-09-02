"""Centralized terminal stream output, styled messaging, and console management."""

from __future__ import annotations

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
        PrintResult,
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
    """Sanitize and mask any sensitive tokens or secrets before standard stream writing."""
    normalized_text = text if isinstance(text, str) else ("" if text is None else str(text))
    from devops_cli.ai.review.sanitization import _mask_secrets_in_content

    return _mask_secrets_in_content(normalized_text)


def write_stream(
    text: str,
    stream: Literal["stdout", "stderr"] = DEFAULT_STREAM_NAME,  # type: ignore[assignment]
    *,
    flush: bool = True,
) -> None:
    """Write raw text directly to standard output or standard error stream."""
    safe_text = _sanitize_output_text(text)
    cons = get_stderr_console() if stream == "stderr" else get_console()
    cons.print(safe_text, markup=False, highlight=False, end="", soft_wrap=True)
    if flush:
        file_obj = getattr(cons, "file", None)
        if file_obj and hasattr(file_obj, "flush"):
            file_obj.flush()


def write_stdout(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard output stream."""
    write_stream(text, stream="stdout", flush=flush)


def write_stderr(text: str, *, flush: bool = True) -> None:
    """Write raw text directly to standard error stream."""
    write_stream(text, stream="stderr", flush=flush)


def escape_text(text: str) -> str:
    """Escape Rich markup tags in string."""
    return _rich_escape(text)


def print(
    content: Any = "",
    *,
    level: MessageLevel = "raw",
    prefix: bool | str | None = None,
    to_stderr: bool = False,
    style: str | None = None,
    title: str | None = None,
    border_style: str | None = None,
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
    box_style: Any = None,
    language: str | None = None,
    line_numbers: bool | None = None,
    start_line: int = CONST_DEFAULT_LINE_NUMBER,
    theme: str | None = None,
    detail: str = "",
    console: Any = None,
    **kwargs: Any,
) -> PrintResult:
    """Unified polymorphic console output engine supporting Pydantic payloads, Rich renderables, and styled text."""
    from devops_cli.output.models import (
        KeyValuePayload,
        MarkdownPayload,
        MessagePayload,
        PanelPayload,
        PrintRequest,
        PrintResult,
        RulePayload,
        SyntaxPayload,
        TablePayload,
    )

    # 1. Unpack PrintRequest payload if supplied
    if isinstance(content, PrintRequest):
        level = content.level
        prefix = content.prefix if prefix is None else prefix
        to_stderr = content.stderr or to_stderr
        title = content.title or title
        border_style = content.border_style or border_style
        content = content.content

    # 2. Unpack MessagePayload if supplied
    if isinstance(content, MessagePayload):
        level = content.level
        prefix = content.prefix if prefix is None else prefix
        content = content.message

    effective_stderr = to_stderr or (level == "error")
    active_console = console or (get_stderr_console() if effective_stderr else get_console())
    stream_name: Literal["stdout", "stderr"] = "stderr" if effective_stderr else "stdout"

    # 3. Pydantic Renderable Models
    if isinstance(content, (TablePayload, KeyValuePayload)):
        active_console.print(content.render())
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="table")

    if isinstance(content, PanelPayload):
        active_console.print(content.render())
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="panel")

    if isinstance(content, MarkdownPayload):
        active_console.print(content.render())
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="markdown")

    if isinstance(content, SyntaxPayload):
        active_console.print(content.render())
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="syntax")

    if isinstance(content, RulePayload):
        active_console.print(content.render())
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="rule")

    if hasattr(content, "render") and not isinstance(
        content, (_RichTable, _RichPanel, _RichMarkdown, _RichSyntax, _RichRule)
    ):
        active_console.print(content.render())
        return PrintResult(
            success=True, level=level, stream=stream_name, rendered_type="renderable"
        )

    # 4. Rich Renderables
    if isinstance(content, (_RichTable, _RichPanel, _RichMarkdown, _RichSyntax, _RichRule)):
        active_console.print(content)
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="rich")

    # 5. Table parameters passed directly
    if columns is not None or rows is not None:
        from devops_cli.output.formatter import render_table

        rendered_table = render_table(
            title=title or (content if isinstance(content, str) else ""),
            columns=columns or [],
            rows=rows or [],
            border_style=border_style or DEFAULT_TABLE_BORDER_STYLE,
            box_style=box_style,
        )
        active_console.print(rendered_table)
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="table")

    # 6. Syntax highlighting
    if language is not None:
        rendered_syntax = _RichSyntax(
            str(content),
            language,
            line_numbers=line_numbers or False,
            start_line=start_line,
            theme=theme or DEFAULT_SYNTAX_THEME,
            **kwargs,
        )
        if title:
            active_console.print(
                _RichPanel(
                    rendered_syntax,
                    title=title,
                    border_style=border_style or DEFAULT_PANEL_BORDER_STYLE,
                )
            )
            return PrintResult(
                success=True, level=level, stream=stream_name, rendered_type="syntax_panel"
            )
        active_console.print(rendered_syntax)
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="syntax")

    # 7. Panel requested via title
    if title is not None and level == "raw":
        active_console.print(
            _RichPanel(
                content,
                title=title,
                border_style=border_style or DEFAULT_PANEL_BORDER_STYLE,
                **kwargs,
            )
        )
        return PrintResult(success=True, level=level, stream=stream_name, rendered_type="panel")

    # 8. Step format
    if level == "step":
        detail_suffix = f" [dim]({detail})[/dim]" if detail else ""
        active_console.print(f"[bold blue]➔[/bold blue] [bold]{content}[/bold]{detail_suffix}")
        return PrintResult(success=True, level="step", stream=stream_name, rendered_type="step")

    # 9. Leveled / Plain string messaging
    formatted_message = str(content)
    if level == "raw":
        active_console.print(formatted_message)
        return PrintResult(success=True, level="raw", stream=stream_name, rendered_type="text")

    defaults: dict[str, tuple[str, str]] = {
        "success": ("bold green", "✓ "),
        "error": ("bold red", "✗ "),
        "warning": ("yellow", "! "),
        "info": ("cyan", "ℹ "),
        "muted": ("dim", ""),
        "step": ("bold blue", "➔ "),
    }

    default_level_style, default_level_prefix = defaults.get(level, ("white", ""))

    if isinstance(prefix, str):
        prefix_symbol = prefix
    elif prefix is not None:
        prefix_symbol = default_level_prefix if prefix else ""
    else:
        prefix_symbol = default_level_prefix

    if style is not None:
        active_console.print(f"[{style}]{prefix_symbol}{formatted_message}[/{style}]")
    elif prefix_symbol:
        if level == "info":
            active_console.print(
                f"[{default_level_style}]{prefix_symbol}[/{default_level_style}]{formatted_message}"
            )
        else:
            active_console.print(
                f"[{default_level_style}]{prefix_symbol}{formatted_message}[/{default_level_style}]"
            )
    else:
        if level in {"error", "warning", "muted", "success", "step"}:
            active_console.print(
                f"[{default_level_style}]{formatted_message}[/{default_level_style}]"
            )
        else:
            active_console.print(formatted_message)

    return PrintResult(success=True, level=level, stream=stream_name, rendered_type="message")


def print_message(
    message: str,
    *,
    level: MessageLevel = DEFAULT_LOG_LEVEL,  # type: ignore[assignment]
    prefix: bool | str = True,
    to_stderr: bool = False,
    style: str | None = None,
    console: Any = None,
) -> None:
    """Print a styled, leveled console message with optional prefix and stream targeting."""
    print(message, level=level, prefix=prefix, to_stderr=to_stderr, style=style, console=console)


def print_success(
    message: str,
    *,
    prefix: bool = True,
    console: Any = None,
) -> None:
    """Print a success message with green styling."""
    print(message, level="success", prefix=prefix, console=console)


def print_error(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print an error message with red styling."""
    print(message, level="error", prefix=prefix, to_stderr=to_stderr, console=console)


def print_warning(
    message: str,
    *,
    prefix: bool = True,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print a warning message with yellow styling."""
    print(message, level="warning", prefix=prefix, to_stderr=to_stderr, console=console)


def print_info(
    message: str,
    *,
    prefix: bool = True,
    console: Any = None,
) -> None:
    """Print an informational message with cyan styling."""
    print(message, level="info", prefix=prefix, console=console)


def print_muted(
    message: str,
    *,
    to_stderr: bool = False,
    console: Any = None,
) -> None:
    """Print a muted/dim message."""
    print(message, level="muted", prefix=False, to_stderr=to_stderr, console=console)


def print_step(
    step: str,
    detail: str = "",
    *,
    console: Any = None,
) -> None:
    """Print a structured execution step."""
    print(step, level="step", detail=detail, console=console)


def print_section(
    title: str | RulePayload = "",
    *,
    style: str = DEFAULT_KEY_STYLE,
    console: Any = None,
) -> None:
    """Print a styled section rule divider."""
    if isinstance(title, str):
        active_console = console or get_console()
        active_console.print(_RichRule(title, style=style))
    else:
        print(title, console=console)


def print_markdown(
    markdown_text: str | MarkdownPayload,
    *,
    console: Any = None,
) -> None:
    """Render and print markdown text."""
    if isinstance(markdown_text, str):
        active_console = console or get_console()
        active_console.print(_RichMarkdown(markdown_text))
    else:
        print(markdown_text, console=console)


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
    if isinstance(code, str):
        print(
            code,
            language=language,
            line_numbers=line_numbers,
            start_line=start_line,
            theme=theme,
            console=console,
            **kwargs,
        )
    else:
        print(code, console=console)


def print_panel(
    renderable: _RichRenderableType | PanelPayload | str,
    *,
    title: str | None = None,
    border_style: str = DEFAULT_PANEL_BORDER_STYLE,
    console: Any = None,
    **kwargs: Any,
) -> None:
    """Render and print a styled Panel."""
    if hasattr(renderable, "render"):
        print(renderable, console=console)
    else:
        active_console = console or get_console()
        active_console.print(
            _RichPanel(renderable, title=title, border_style=border_style, **kwargs)
        )


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
    """Render and print a styled table to the console."""
    print(
        table_or_title,
        columns=columns,
        rows=rows,
        title=title,
        border_style=border_style,
        box_style=box_style,
        console=console,
    )


def print_key_values(
    title: str,
    items: dict[str, Any] | list[tuple[str, Any]],
    *,
    key_style: str = DEFAULT_KEY_STYLE,
    value_style: str = DEFAULT_VALUE_STYLE,
    console: Any = None,
) -> None:
    """Render and print a key-value summary table to the console."""
    from devops_cli.output.models import KeyValuePayload

    pairs = dict(items) if isinstance(items, list) else items
    kv = KeyValuePayload(title=title, items=pairs, key_style=key_style, value_style=value_style)
    print(kv, console=console)


def track_progress[T](
    iterable: Iterable[T],
    description: str = DEFAULT_PROGRESS_DESC_WORKING,
    *,
    console: Any = None,
) -> Generator[T]:
    """Iterate with Rich progress bar tracking."""
    active_console = console or get_console()
    yield from _rich_track(iterable, description=description, console=active_console)


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
    active_console = console or get_console()
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
    active_console.print(_RichPanel(syntax, title=title, border_style=border_style))


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
    active_console = console or get_console()
    with _RichProgress(
        _RichSpinnerColumn(),
        _RichTextColumn("[progress.description]{task.description}"),
        _RichBarColumn(),
        _RichTextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=active_console,
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

    active_console = console or get_console()
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
    active_console.print(msg_template.format(command=rendered))


def print_dry_run_result(
    result: Any,
    *,
    console: Any = None,
) -> None:
    """Print structured CommandDryRunResult JSON for dry-run mode."""
    from devops_cli.lang.en.messages import MESSAGES

    active_console = console or get_console()
    active_console.print(MESSAGES.dry_run.command_response_header)
    dump_fn = getattr(result, "model_dump_json", None)
    if callable(dump_fn):
        active_console.print_json(dump_fn(indent=2))
    elif isinstance(result, str):
        active_console.print_json(result)
    else:
        import json

        active_console.print_json(json.dumps(result, indent=2, default=str))


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
    "print",
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
